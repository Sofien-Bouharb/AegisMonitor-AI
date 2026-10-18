
from datetime import datetime, timedelta, timezone

from ml.correlation.engine import (
    CorrelationEngine,
    Severity,
    Signal,
    SignalType,
)


def main():
    start = datetime.now(timezone.utc)

    signals = [
        Signal(
            signal_type=SignalType.ANOMALY,
            name="CPU anomaly candidate",
            occurred_at=start,
            severity=Severity.WARNING,
            source="isolation-forest",
            message="Unusual CPU-related telemetry detected.",
        ),
        Signal(
            signal_type=SignalType.ALERT,
            name="HighCPUUsage",
            occurred_at=start + timedelta(seconds=30),
            severity=Severity.WARNING,
            source="prometheus",
            message="CPU usage exceeded the configured threshold.",
        ),
        Signal(
            signal_type=SignalType.LOG_SIGNATURE,
            name="ath9k signature burst",
            occurred_at=start + timedelta(seconds=60),
            severity=Severity.WARNING,
            source="fluent-bit",
            message="Repeated Wi-Fi driver log signature observed.",
            metadata={"occurrence_count": 12},
        ),
    ]

    engine = CorrelationEngine(window=timedelta(minutes=5))
    incidents = engine.correlate(signals)

    print("=== AegisMonitor P17 Correlation Demo ===")
    print(f"Input signals: {len(signals)}")
    print(f"Incidents created: {len(incidents)}")

    for incident in incidents:
        print(f"\nIncident ID: {incident.incident_id}")
        print(f"Title: {incident.title}")
        print(f"Host: {incident.host}")
        print(f"Severity: {incident.severity.value}")
        print(f"Status: {incident.status}")
        print(f"Rationale: {incident.rationale}")
        print("\nRelationships:")

        for relationship in incident.relationships:
            print(
                f"  - {relationship.signal_type.value}: "
                f"{relationship.signal_name} | "
                f"role={relationship.role.value} | "
                f"relevance={relationship.relevance:.2f}"
            )

    if len(incidents) != 1:
        raise SystemExit("FAIL: Expected exactly one correlated incident.")

    print("\nPASS: Multiple signal types produced one incident.")


if __name__ == "__main__":
    main()
