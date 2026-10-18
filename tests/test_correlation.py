
import unittest
from datetime import datetime, timedelta, timezone

from ml.correlation.engine import (
    CorrelationEngine,
    RelationshipRole,
    Severity,
    Signal,
    SignalType,
)


class TestCorrelationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CorrelationEngine(window=timedelta(minutes=5))
        self.base_time = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)

    def make_signal(
        self,
        signal_type,
        name,
        minutes=0,
        severity=Severity.WARNING,
        host="localhost",
    ):
        return Signal(
            signal_type=signal_type,
            name=name,
            occurred_at=self.base_time + timedelta(minutes=minutes),
            severity=severity,
            host=host,
            source="test",
        )

    def test_multiple_signal_types_create_one_incident(self):
        signals = [
            self.make_signal(
                SignalType.ANOMALY,
                "CPU anomaly candidate",
                severity=Severity.WARNING,
            ),
            self.make_signal(
                SignalType.ALERT,
                "HighCPUUsage",
                minutes=1,
                severity=Severity.WARNING,
            ),
            self.make_signal(
                SignalType.LOG_SIGNATURE,
                "ath9k signature burst",
                minutes=2,
                severity=Severity.WARNING,
            ),
        ]

        incidents = self.engine.correlate(signals)

        self.assertEqual(len(incidents), 1)
        incident = incidents[0]
        self.assertEqual(incident.host, "localhost")
        self.assertEqual(incident.status, "open")
        self.assertEqual(len(incident.relationships), 3)
        self.assertEqual(
            {r.signal_type for r in incident.relationships},
            {
                SignalType.ANOMALY,
                SignalType.ALERT,
                SignalType.LOG_SIGNATURE,
            },
        )
        self.assertTrue(all(0 <= r.relevance <= 1 for r in incident.relationships))

    def test_anomaly_candidate_alone_does_not_create_incident(self):
        signals = [
            self.make_signal(SignalType.ANOMALY, "CPU anomaly candidate")
        ]

        self.assertEqual(self.engine.correlate(signals), [])

    def test_anomaly_and_alert_create_incident(self):
        signals = [
            self.make_signal(SignalType.ANOMALY, "CPU anomaly candidate"),
            self.make_signal(
                SignalType.ALERT, "HighCPUUsage", minutes=1
            ),
        ]

        incidents = self.engine.correlate(signals)

        self.assertEqual(len(incidents), 1)
        self.assertEqual(len(incidents[0].relationships), 2)

    def test_signals_outside_time_window_are_not_correlated(self):
        signals = [
            self.make_signal(SignalType.ANOMALY, "CPU anomaly candidate"),
            self.make_signal(
                SignalType.ALERT, "HighCPUUsage", minutes=6
            ),
        ]

        self.assertEqual(self.engine.correlate(signals), [])

    def test_signals_from_other_hosts_are_ignored(self):
        signals = [
            self.make_signal(
                SignalType.ANOMALY,
                "CPU anomaly candidate",
                host="localhost",
            ),
            self.make_signal(
                SignalType.ALERT,
                "HighCPUUsage",
                minutes=1,
                host="other-host",
            ),
        ]

        self.assertEqual(self.engine.correlate(signals), [])

    def test_relationships_preserve_signal_ids_and_timestamps(self):
        anomaly = self.make_signal(SignalType.ANOMALY, "CPU anomaly")
        alert = self.make_signal(
            SignalType.ALERT, "HighCPUUsage", minutes=1
        )

        incident = self.engine.correlate([anomaly, alert])[0]
        relationship_ids = {r.signal_id for r in incident.relationships}

        self.assertEqual(relationship_ids, {anomaly.signal_id, alert.signal_id})
        self.assertEqual(
            incident.created_at,
            min(anomaly.occurred_at, alert.occurred_at),
        )
        self.assertEqual(
            incident.updated_at,
            max(anomaly.occurred_at, alert.occurred_at),
        )

    def test_relationships_have_explicit_roles(self):
        signals = [
            self.make_signal(
                SignalType.ALERT,
                "HighCPUUsage",
                severity=Severity.CRITICAL,
            ),
            self.make_signal(
                SignalType.ANOMALY,
                "CPU anomaly candidate",
                minutes=1,
            ),
        ]

        incident = self.engine.correlate(signals)[0]
        roles = {r.role for r in incident.relationships}

        self.assertIn(RelationshipRole.PRIMARY, roles)
        self.assertIn(RelationshipRole.SUPPORTING, roles)


if __name__ == "__main__":
    unittest.main()
