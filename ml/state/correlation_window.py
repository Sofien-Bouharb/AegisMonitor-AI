"""Redis-backed temporary signal storage for correlation windows."""

import json
import os
from datetime import datetime, timedelta, timezone

import redis

from ml.correlation.engine import Signal, SignalType, Severity


DEFAULT_WINDOW_SECONDS = 300
KEY_PREFIX = "aegis:correlation:host:"


def correlation_window_seconds() -> int:
    """Read the correlation-window duration from the environment."""
    value = int(
        os.getenv(
            "REDIS_CORRELATION_WINDOW_SECONDS",
            str(DEFAULT_WINDOW_SECONDS),
        )
    )
    if value <= 0:
        raise ValueError("REDIS_CORRELATION_WINDOW_SECONDS must be positive")
    return value


def host_signal_key(host: str) -> str:
    """Return the Redis sorted-set key for one host's recent signals."""
    if not host or not host.strip():
        raise ValueError("Host cannot be empty")
    return f"{KEY_PREFIX}{host}"


def host_payload_key(host: str) -> str:
    """Return the Redis hash key containing signal payloads for one host."""
    return f"{host_signal_key(host)}:payloads"


def serialize_signal(signal: Signal) -> str:
    """Serialize a signal into JSON for temporary Redis storage."""
    return json.dumps(
        {
            "signal_type": signal.signal_type.value,
            "name": signal.name,
            "occurred_at": signal.occurred_at.isoformat(),
            "severity": signal.severity.value,
            "host": signal.host,
            "source": signal.source,
            "message": signal.message,
            "metadata": signal.metadata,
            "signal_id": signal.signal_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def deserialize_signal(value: str) -> Signal:
    """Restore a Signal from its JSON representation."""
    data = json.loads(value)
    return Signal(
        signal_type=SignalType(data["signal_type"]),
        name=data["name"],
        occurred_at=datetime.fromisoformat(data["occurred_at"]),
        severity=Severity(data["severity"]),
        host=data["host"],
        source=data["source"],
        message=data["message"],
        metadata=data["metadata"],
        signal_id=data["signal_id"],
    )


def store_signal(
    client: redis.Redis,
    signal: Signal,
    *,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    now: datetime | None = None,
) -> list[Signal]:
    """Store a signal and return signals still inside its correlation window."""
    if window_seconds <= 0:
        raise ValueError("window_seconds must be positive")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError("Current time must include a timezone")
    current_time = current_time.astimezone(timezone.utc)

    key = host_signal_key(signal.host)
    payload_key = host_payload_key(signal.host)
    cutoff = current_time - timedelta(seconds=window_seconds)

    client.zadd(key, {signal.signal_id: signal.occurred_at.timestamp()})
    client.hset(payload_key, signal.signal_id, serialize_signal(signal))

    # Remove expired signals from both the timestamp index and payload hash.
    expired_ids = client.zrangebyscore(
        key,
        "-inf",
        cutoff.timestamp(),
    )
    if expired_ids:
        client.zrem(key, *expired_ids)
        client.hdel(payload_key, *expired_ids)

    # Expire idle host state so unused keys do not live indefinitely.
    client.expire(key, window_seconds)
    client.expire(payload_key, window_seconds)

    entries = client.zrangebyscore(key, cutoff.timestamp(), "+inf")
    if not entries:
        return []

    payloads = client.hmget(payload_key, entries)
    return [
        deserialize_signal(payload)
        for payload in payloads
        if payload is not None
    ]