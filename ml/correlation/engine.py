
"""Deterministic, single-host signal correlation for AegisMonitor P17."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable
from uuid import uuid4


class SignalType(str, Enum):
    ALERT = "alert"
    ANOMALY = "anomaly"
    LOG_SIGNATURE = "log_signature"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RelationshipRole(str, Enum):
    PRIMARY = "primary"
    CONTRIBUTING = "contributing"
    SUPPORTING = "supporting"
    EVIDENCE = "evidence"


SEVERITY_WEIGHT = {
    Severity.INFO: 1,
    Severity.WARNING: 2,
    Severity.CRITICAL: 3,
}

ROLE_WEIGHT = {
    RelationshipRole.PRIMARY: 1.0,
    RelationshipRole.CONTRIBUTING: 0.85,
    RelationshipRole.SUPPORTING: 0.65,
    RelationshipRole.EVIDENCE: 0.5,
}


def normalize_timestamp(value: datetime) -> datetime:
    """Convert a timezone-aware timestamp to UTC."""
    if value.tzinfo is None:
        raise ValueError("Signal timestamps must include a timezone.")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Signal:
    """An alert, anomaly candidate, or log-signature burst."""

    signal_type: SignalType
    name: str
    occurred_at: datetime
    severity: Severity
    host: str = "localhost"
    source: str = ""
    message: str = ""
    metadata: dict = field(default_factory=dict)
    signal_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        object.__setattr__(
            self, "occurred_at", normalize_timestamp(self.occurred_at)
        )
        if not self.name.strip():
            raise ValueError("Signal name cannot be empty.")
        if not self.host.strip():
            raise ValueError("Signal host cannot be empty.")


@dataclass(frozen=True)
class IncidentRelationship:
    """Explicit relationship between an incident and a signal."""

    signal_id: str
    signal_type: SignalType
    signal_name: str
    role: RelationshipRole
    relevance: float
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class Incident:
    """A correlated group of signals."""

    incident_id: str
    title: str
    host: str
    severity: Severity
    status: str
    created_at: datetime
    updated_at: datetime
    relationships: tuple[IncidentRelationship, ...]
    rationale: str


class CorrelationEngine:
    """Group related signals into incidents using deterministic rules."""

    def __init__(
        self,
        window: timedelta = timedelta(minutes=5),
        host: str = "localhost",
        min_distinct_types: int = 2,
    ):
        if window <= timedelta(0):
            raise ValueError("Correlation window must be positive.")
        if min_distinct_types < 2:
            raise ValueError("At least two signal types are required.")

        self.window = window
        self.host = host
        self.min_distinct_types = min_distinct_types

    def correlate(self, signals: Iterable[Signal]) -> list[Incident]:
        """Return incidents for qualifying groups in the supplied signals."""
        eligible = sorted(
            (s for s in signals if s.host == self.host),
            key=lambda s: (s.occurred_at, s.signal_id),
        )

        groups = []
        for signal in eligible:
            if (
                not groups
                or signal.occurred_at - groups[-1][0].occurred_at
                > self.window
            ):
                groups.append([signal])
            else:
                groups[-1].append(signal)

        incidents = []
        for group in groups:
            distinct_types = {signal.signal_type for signal in group}
            has_corroboration = any(
                signal.signal_type != SignalType.ANOMALY
                for signal in group
            )

            # An anomaly candidate alone is never an incident.
            if (
                len(distinct_types) < self.min_distinct_types
                or not has_corroboration
            ):
                continue

            incidents.append(self._build_incident(group))

        return incidents

    def _build_incident(self, signals: list[Signal]) -> Incident:
        # Choose the most severe signal as the primary evidence.
        ordered = sorted(
            signals,
            key=lambda s: (
                SEVERITY_WEIGHT[s.severity],
                s.occurred_at,
                s.signal_id,
            ),
            reverse=True,
        )
        primary = ordered[0]
        relationships = []

        for signal in signals:
            if signal.signal_id == primary.signal_id:
                role = RelationshipRole.PRIMARY
            elif signal.signal_type == SignalType.ANOMALY:
                role = RelationshipRole.SUPPORTING
            elif signal.severity == Severity.CRITICAL:
                role = RelationshipRole.CONTRIBUTING
            else:
                role = RelationshipRole.EVIDENCE

            relevance = round(
                SEVERITY_WEIGHT[signal.severity]
                / 3
                * ROLE_WEIGHT[role],
                2,
            )

            relationships.append(
                IncidentRelationship(
                    signal_id=signal.signal_id,
                    signal_type=signal.signal_type,
                    signal_name=signal.name,
                    role=role,
                    relevance=relevance,
                    first_seen_at=signal.occurred_at,
                    last_seen_at=signal.occurred_at,
                )
            )

        role_by_id = {
            relationship.signal_id: relationship.role
            for relationship in relationships
        }

        weighted_score = sum(
            SEVERITY_WEIGHT[signal.severity]
            * ROLE_WEIGHT[role_by_id[signal.signal_id]]
            for signal in signals
        )
        distinct_types = {signal.signal_type for signal in signals}

        if weighted_score >= 5 and len(distinct_types) >= 3:
            incident_severity = Severity.CRITICAL
        elif weighted_score >= 3:
            incident_severity = Severity.WARNING
        else:
            incident_severity = Severity.INFO

        type_names = ", ".join(
            sorted(signal_type.value for signal_type in distinct_types)
        )
        rationale = (
            f"{len(signals)} signals from {len(distinct_types)} distinct "
            f"types occurred within {self.window}. "
            f"Correlated types: {type_names}. "
            f"Weighted evidence score: {weighted_score:.2f}."
        )

        return Incident(
            incident_id=str(uuid4()),
            title=f"Correlated host activity on {self.host}",
            host=self.host,
            severity=incident_severity,
            status="open",
            created_at=min(s.occurred_at for s in signals),
            updated_at=max(s.occurred_at for s in signals),
            relationships=tuple(relationships),
            rationale=rationale,
        )
