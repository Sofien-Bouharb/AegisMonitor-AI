import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from ml.alert_receiver.app import parse_timestamp, persist_alert


class AlertReceiverTests(unittest.TestCase):
    def setUp(self):
        self.alert = {
            "fingerprint": "test-fingerprint",
            "status": "firing",
            "labels": {
                "alertname": "HighCPUUsage",
                "severity": "warning",
                "instance": "localhost:9100",
            },
            "annotations": {"summary": "CPU usage is high"},
            "startsAt": "2026-10-19T12:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }

    def test_parse_timestamp_normalizes_utc(self):
        result = parse_timestamp("2026-10-19T13:00:00+01:00")
        self.assertEqual(
            result,
            datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
        )

    @patch("ml.alert_receiver.app.save_alert")
    @patch("ml.alert_receiver.app.connect")
    def test_persists_firing_alert(self, mock_connect, mock_save):
        conn = mock_connect.return_value

        persist_alert(self.alert)

        mock_connect.assert_called_once_with()
        mock_save.assert_called_once()
        self.assertIs(mock_save.call_args.args[0], conn)
        self.assertEqual(
            mock_save.call_args.kwargs["fingerprint"],
            "test-fingerprint",
        )
        self.assertEqual(mock_save.call_args.kwargs["status"], "firing")
        self.assertEqual(
            mock_save.call_args.kwargs["host"],
            "localhost:9100",
        )

    @patch("ml.alert_receiver.app.save_alert")
    @patch("ml.alert_receiver.app.connect")
    def test_persists_resolved_alert(self, mock_connect, mock_save):
        self.alert["status"] = "resolved"
        self.alert["endsAt"] = "2026-10-19T12:05:00Z"

        persist_alert(self.alert)

        self.assertEqual(mock_save.call_args.kwargs["status"], "resolved")
        self.assertEqual(
            mock_save.call_args.kwargs["resolved_at"],
            datetime(2026, 10, 19, 12, 5, tzinfo=timezone.utc),
        )

    @patch("ml.alert_receiver.app.connect")
    def test_rejects_missing_fingerprint(self, mock_connect):
        del self.alert["fingerprint"]

        with self.assertRaisesRegex(ValueError, "fingerprint is required"):
            persist_alert(self.alert)

        mock_connect.assert_not_called()

    @patch("ml.alert_receiver.app.connect")
    def test_rejects_resolved_alert_without_end_timestamp(self, mock_connect):
        self.alert["status"] = "resolved"
        self.alert["endsAt"] = ""

        with self.assertRaisesRegex(ValueError, "requires endsAt"):
            persist_alert(self.alert)

        mock_connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
