
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

from ml.correlation.engine import (
    Incident,
    IncidentRelationship,
    RelationshipRole,
    Severity,
    SignalType,
)
from ml.database.repository import (
    list_recent_incidents,
    save_alert,
    save_incident,
)

class IncidentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.timestamp = datetime(
            2026, 10, 19, 12, 0, tzinfo=timezone.utc
        )
        self.incident = Incident(
            incident_id="00000000-0000-0000-0000-000000000001",
            title="Correlated host activity on localhost",
            host="localhost",
            severity=Severity.WARNING,
            status="open",
            created_at=self.timestamp,
            updated_at=self.timestamp,
            relationships=(
                IncidentRelationship(
                    signal_id="00000000-0000-0000-0000-000000000002",
                    signal_type=SignalType.ALERT,
                    signal_name="HighCPUUsage",
                    role=RelationshipRole.PRIMARY,
                    relevance=0.67,
                    first_seen_at=self.timestamp,
                    last_seen_at=self.timestamp,
                ),
            ),
            rationale="Alert and anomaly evidence were correlated.",
        )
        self.conn = MagicMock()
        self.cursor = (
            self.conn.cursor.return_value.__enter__.return_value
        )

    def test_saves_incident_and_existing_alert_relationship(self):
        save_incident(self.conn, self.incident)

        incident_insert = next(
            executed
            for executed in self.cursor.execute.call_args_list
            if "INSERT INTO incidents" in executed.args[0]
        )

        self.assertEqual(
            incident_insert.args[1],
            (
                self.incident.incident_id,
                self.incident.title,
                self.incident.rationale,
                self.incident.status,
                self.incident.severity.value,
                self.incident.host,
                self.incident.created_at,
                self.incident.updated_at,
            ),
        )

        self.conn.transaction.assert_called_once()
        self.conn.cursor.assert_called_once()

        statements = [
            executed.args[0]
            for executed in self.cursor.execute.call_args_list
        ]
        self.assertTrue(
            any("INSERT INTO incidents" in sql for sql in statements)
        )
        self.assertTrue(
            any("INSERT INTO incident_alerts" in sql for sql in statements)
        )

    def test_unsupported_signal_type_is_rejected(self):
        relationship = self.incident.relationships[0]
        unsupported_relationship = IncidentRelationship(
            signal_id=relationship.signal_id,
            signal_type=SignalType.LOG_SIGNATURE,
            signal_name=relationship.signal_name,
            role=relationship.role,
            relevance=relationship.relevance,
            first_seen_at=relationship.first_seen_at,
            last_seen_at=relationship.last_seen_at,
        )
        unsupported_incident = Incident(
            **{
                **self.incident.__dict__,
                "relationships": (unsupported_relationship,),
            }
        )

        with self.assertRaises(NotImplementedError):
            save_incident(self.conn, unsupported_incident)

        self.conn.cursor.assert_not_called()
        self.conn.transaction.assert_not_called()

    def test_saves_anomaly_relationship_to_correct_table(self):
        anomaly_relationship = IncidentRelationship(
            signal_id="00000000-0000-0000-0000-000000000003",
            signal_type=SignalType.ANOMALY,
            signal_name="CPU anomaly candidate",
            role=RelationshipRole.CONTRIBUTING,
            relevance=0.5,
            first_seen_at=self.timestamp,
            last_seen_at=self.timestamp,
        )
        anomaly_incident = Incident(
            **{
                **self.incident.__dict__,
                "relationships": (anomaly_relationship,),
            }
        )

        save_incident(self.conn, anomaly_incident)

        statements = [
            executed.args[0]
            for executed in self.cursor.execute.call_args_list
        ]
        self.assertTrue(
            any(
                "INSERT INTO incident_anomalies" in sql
                for sql in statements
            )
        )
        self.assertFalse(
            any(
                "INSERT INTO incident_alerts" in sql
                for sql in statements
            )
        )

    def test_relationship_failure_rolls_back_transaction(self):
        self.cursor.execute.side_effect = [
            None,
            RuntimeError("Evidence insert failed"),
        ]

        with self.assertRaisesRegex(
            RuntimeError, "Evidence insert failed"
        ):
            save_incident(self.conn, self.incident)

        self.conn.transaction.assert_called_once()
        exit_call = self.conn.transaction.return_value.__exit__
        exit_call.assert_called_once()
        self.assertIsNotNone(exit_call.call_args.args[0])


if __name__ == "__main__":
    unittest.main()


class AlertRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.timestamp = datetime(
            2026, 10, 19, 12, 0, tzinfo=timezone.utc
        )
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value.__enter__.return_value

    def save_sample_alert(self, **overrides):
        alert = {
            "fingerprint": "stable-fingerprint-123",
            "rule_name": "HighCPUUsage",
            "source": "alertmanager",
            "severity": "warning",
            "status": "firing",
            "fired_at": self.timestamp,
            "labels": {"alertname": "HighCPUUsage", "instance": "localhost"},
            "annotations": {"summary": "High CPU usage"},
            "host": "localhost",
        }
        alert.update(overrides)
        save_alert(self.conn, **alert)

    def test_inserts_alert_with_fingerprint_upsert(self):
        self.save_sample_alert()

        query = self.cursor.execute.call_args.args[0]
        params = self.cursor.execute.call_args.args[1]

        self.assertIn("INSERT INTO alerts", query)
        self.assertIn("ON CONFLICT (fingerprint) DO UPDATE", query)
        self.assertEqual(params[0], "stable-fingerprint-123")
        self.assertEqual(params[1], "HighCPUUsage")
        self.assertEqual(params[7], "firing")
        self.assertIsNone(params[9])
        self.conn.transaction.assert_called_once()

    def test_resolved_alert_persists_resolution_timestamp(self):
        self.save_sample_alert(
            status="resolved",
            resolved_at=self.timestamp,
        )

        params = self.cursor.execute.call_args.args[1]
        self.assertEqual(params[7], "resolved")
        self.assertEqual(params[9], self.timestamp)

    def test_firing_again_clears_resolution_timestamp(self):
        self.save_sample_alert(
            status="firing",
            resolved_at=self.timestamp,
        )

        params = self.cursor.execute.call_args.args[1]
        self.assertEqual(params[7], "firing")
        self.assertIsNone(params[9])

    def test_rejects_invalid_status_before_database_access(self):
        with self.assertRaisesRegex(ValueError, "Unsupported alert status"):
            self.save_sample_alert(status="pending")

        self.conn.transaction.assert_not_called()

    def test_resolved_alert_requires_resolution_timestamp(self):
        with self.assertRaisesRegex(
            ValueError, "requires resolved_at"
        ):
            self.save_sample_alert(status="resolved")

        self.conn.transaction.assert_not_called()

    def test_rejects_invalid_severity_before_database_access(self):
        with self.assertRaisesRegex(
            ValueError, "Unsupported alert severity"
        ):
            self.save_sample_alert(severity="emergency")

        self.conn.transaction.assert_not_called()



if __name__ == "__main__":
    unittest.main()



class RecentIncidentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value.__enter__.return_value

    def test_returns_recent_incidents_as_dictionaries(self):
        self.cursor.description = [
            MagicMock(name="id"),
            MagicMock(name="title"),
        ]
        # Set .name explicitly because MagicMock's constructor name
        # parameter does not set the attribute used by the repository.
        self.cursor.description[0].name = "id"
        self.cursor.description[1].name = "title"
        self.cursor.fetchall.return_value = [
            ("incident-1", "Recent incident"),
            ("incident-2", "Older incident"),
        ]

        result = list_recent_incidents(self.conn, limit=10)

        self.assertEqual(
            result,
            [
                {"id": "incident-1", "title": "Recent incident"},
                {"id": "incident-2", "title": "Older incident"},
            ],
        )
        query, params = self.cursor.execute.call_args.args
        self.assertIn("FROM incidents", query)
        self.assertIn("ORDER BY opened_at DESC, id DESC", query)
        self.assertIn("LIMIT %s", query)
        self.assertEqual(params, (10,))

    def test_returns_empty_list_when_no_incidents_exist(self):
        self.cursor.description = [MagicMock()]
        self.cursor.description[0].name = "id"
        self.cursor.fetchall.return_value = []

        self.assertEqual(list_recent_incidents(self.conn), [])

    def test_rejects_invalid_limits_before_database_access(self):
        for limit in (0, 101, True, 1.5, "10", None):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    list_recent_incidents(self.conn, limit=limit)

        self.conn.cursor.assert_not_called()

class AIRepositoryTests(unittest.TestCase):
    def setUp(self):
        from uuid import UUID

        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value.__enter__.return_value
        self.analysis_id = UUID("00000000-0000-0000-0000-000000000010")
        self.feedback_id = UUID("00000000-0000-0000-0000-000000000011")

    def test_saves_ai_analysis_and_returns_id(self):
        from ml.database.repository import save_ai_analysis

        self.cursor.fetchone.return_value = (self.analysis_id,)
        context = {"host": "localhost", "metrics": {"cpu_usage_pct": 95.0}}

        result = save_ai_analysis(
            self.conn,
            analysis="CPU usage is unusually high.",
            context=context,
        )

        self.assertEqual(result, str(self.analysis_id))
        query, params = self.cursor.execute.call_args.args
        self.assertIn("INSERT INTO ai_analyses", query)
        self.assertIn("RETURNING id", query)
        self.assertEqual(params[0], "CPU usage is unusually high.")
        self.assertEqual(params[1].obj, context)
        self.conn.transaction.assert_called_once()

    def test_rejects_blank_analysis_before_database_access(self):
        from ml.database.repository import save_ai_analysis

        for analysis in ("", "   "):
            with self.subTest(analysis=repr(analysis)):
                with self.assertRaisesRegex(ValueError, "analysis cannot be blank"):
                    save_ai_analysis(
                        self.conn,
                        analysis=analysis,
                        context={},
                    )

        self.conn.cursor.assert_not_called()
        self.conn.transaction.assert_not_called()

    def test_rejects_non_dictionary_analysis_context(self):
        from ml.database.repository import save_ai_analysis

        with self.assertRaisesRegex(ValueError, "context must be a dictionary"):
            save_ai_analysis(
                self.conn,
                analysis="Example analysis",
                context=[],
            )

        self.conn.cursor.assert_not_called()

    def test_saves_feedback_for_analysis_and_returns_id(self):
        from ml.database.repository import save_ai_feedback

        self.cursor.fetchone.return_value = (self.feedback_id,)
        result = save_ai_feedback(
            self.conn,
            analysis_id=str(self.analysis_id),
            verdict="helpful",
            comment="The explanation matches the metrics.",
        )

        self.assertEqual(result, str(self.feedback_id))
        query, params = self.cursor.execute.call_args.args
        self.assertIn("INSERT INTO ai_feedback", query)
        self.assertIn("RETURNING id", query)
        self.assertEqual(str(params[0]), str(self.analysis_id))
        self.assertEqual(params[1:], (
            "helpful",
            "The explanation matches the metrics.",
        ))
        self.conn.transaction.assert_called_once()

    def test_rejects_unsupported_feedback_verdict(self):
        from ml.database.repository import save_ai_feedback

        with self.assertRaisesRegex(ValueError, "Unsupported feedback verdict"):
            save_ai_feedback(
                self.conn,
                analysis_id=str(self.analysis_id),
                verdict="maybe",
            )

        self.conn.cursor.assert_not_called()
        self.conn.transaction.assert_not_called()

    def test_rejects_invalid_analysis_id(self):
        from ml.database.repository import save_ai_feedback

        with self.assertRaisesRegex(ValueError, "valid UUID"):
            save_ai_feedback(
                self.conn,
                analysis_id="not-a-uuid",
                verdict="correct",
            )

        self.conn.cursor.assert_not_called()

    def test_rejects_non_string_feedback_comment(self):
        from ml.database.repository import save_ai_feedback

        with self.assertRaisesRegex(ValueError, "comment must be a string"):
            save_ai_feedback(
                self.conn,
                analysis_id=str(self.analysis_id),
                verdict="incorrect",
                comment=123,
            )

        self.conn.cursor.assert_not_called()
