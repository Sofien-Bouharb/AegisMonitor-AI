"""FastAPI endpoints for the AegisMonitor correlation engine."""

from datetime import datetime
from typing import Any

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ml.correlation.engine import (
    CorrelationEngine,
    Incident,
    Severity,
    Signal,
    SignalType,
)
from ml.state.correlation_window import correlation_window_seconds, store_signal
from ml.state.redis_client import create_client


app = FastAPI(
    title="AegisMonitor API",
    description="Structured signal correlation API.",
    version="0.1.0",
)


class SignalInput(BaseModel):
    """Validated API representation of a correlation signal."""

    model_config = ConfigDict(extra="forbid")

    signal_type: SignalType
    name: str = Field(min_length=1)
    occurred_at: datetime
    severity: Severity
    host: str = Field(default="localhost", min_length=1)
    source: str = ""
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    signal_id: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("name", "host")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value cannot be blank")
        return value


class CorrelationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[SignalInput] = Field(max_length=1000)


def _serialize_incident(incident: Incident) -> dict[str, Any]:
    """Convert correlation dataclasses into JSON-compatible values."""
    return {
        "incident_id": incident.incident_id,
        "title": incident.title,
        "host": incident.host,
        "severity": incident.severity.value,
        "status": incident.status,
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat(),
        "rationale": incident.rationale,
        "relationships": [
            {
                "signal_id": relationship.signal_id,
                "signal_type": relationship.signal_type.value,
                "signal_name": relationship.signal_name,
                "role": relationship.role.value,
                "relevance": relationship.relevance,
                "first_seen_at": relationship.first_seen_at.isoformat(),
                "last_seen_at": relationship.last_seen_at.isoformat(),
            }
            for relationship in incident.relationships
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Report process-level API health only."""
    return {"status": "ok"}


@app.post("/api/v1/correlate")
def correlate(request: CorrelationRequest) -> dict[str, Any]:
    """Correlate supplied signals with recent Redis-backed host signals."""
    signals = [
        Signal(
            signal_type=item.signal_type,
            name=item.name,
            occurred_at=item.occurred_at,
            severity=item.severity,
            host=item.host,
            source=item.source,
            message=item.message,
            metadata=item.metadata,
            **({"signal_id": item.signal_id} if item.signal_id else {}),
        )
        for item in request.signals
    ]

    if not signals:
        return {"incident_count": 0, "incidents": []}

    client = create_client()
    recent_by_host: dict[str, list[Signal]] = {}
    try:
        window_seconds = correlation_window_seconds()
        for signal in signals:
            recent_by_host[signal.host] = store_signal(
                client,
                signal,
                window_seconds=window_seconds,
            )
    except redis.RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail="Correlation state is temporarily unavailable.",
        ) from exc
    finally:
        client.close()

    recent_signals = {
        (signal.host, signal.signal_id): signal
        for host_signals in recent_by_host.values()
        for signal in host_signals
    }
    signals_by_host: dict[str, list[Signal]] = {}
    for signal in recent_signals.values():
        signals_by_host.setdefault(signal.host, []).append(signal)

    incidents = []
    for host, host_signals in signals_by_host.items():
        incidents.extend(
            CorrelationEngine(host=host).correlate(host_signals)
        )

    return {
        "incident_count": len(incidents),
        "incidents": [_serialize_incident(incident) for incident in incidents],
    }
