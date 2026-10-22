"""Tests for the structured anomaly context collector."""

import unittest
from unittest.mock import patch

from ml.api.incident_context import collect_anomaly_context
from ml.api.prometheus_client import PrometheusError
from ml.api.loki_client import LokiError

from datetime import datetime, timezone




class IncidentContextTests(unittest.TestCase):
    @patch("ml.api.incident_context.query_recent_logs", return_value=[])
    @patch("ml.api.incident_context.query_instant")
    def test_collects_available_metrics(self, mock_query, mock_logs):
        mock_query.side_effect = [
            [{"value": [1792600000, "-0.71"]}],
            [{"value": [1792600000, "1"]}],
            [{"value": [1792600000, "1"]}],
            [{"value": [1792599990, "1792599990"]}],
        ]

        context = collect_anomaly_context()

        self.assertEqual(context["source"], "prometheus")
        self.assertEqual(
            context["metrics"]["anomaly_score"],
            {"status": "available", "value": -0.71},
        )
        self.assertEqual(
            context["metrics"]["anomaly_candidate"]["value"], 1.0
        )
        self.assertEqual(mock_query.call_count, 4)


    @patch("ml.api.incident_context.query_recent_logs", return_value=[])
    @patch("ml.api.incident_context.query_instant")
    def test_missing_metric_is_unavailable_not_zero(self, mock_query, mock_logs):
        mock_query.side_effect = [
            [],
            [{"value": [1792600000, "0"]}],
            [{"value": [1792600000, "1"]}],
            [{"value": [1792599990, "1792599990"]}],
        ]

        context = collect_anomaly_context()

        self.assertEqual(
            context["metrics"]["anomaly_score"],
            {"status": "unavailable", "value": None},
        )

    @patch("ml.api.incident_context.query_instant")
    def test_rejects_multiple_series_for_single_metric(self, mock_query):
        mock_query.return_value = [
            {"value": [1792600000, "1"]},
            {"value": [1792600000, "2"]},
        ]

        with self.assertRaises(PrometheusError):
            collect_anomaly_context()

    @patch("ml.api.incident_context.query_instant")
    def test_prometheus_failure_is_propagated(self, mock_query):
        mock_query.side_effect = PrometheusError("Prometheus unavailable")

        with self.assertRaises(PrometheusError):
            collect_anomaly_context()

    @patch("ml.api.incident_context.query_instant")
    def test_rejects_non_numeric_metric_sample(self, mock_query):
        mock_query.side_effect = [
            [{"value": [1792600000, "not-a-number"]}],
        ]

        with self.assertRaises(PrometheusError):
            collect_anomaly_context()


    @patch("ml.api.incident_context.query_recent_logs")
    @patch("ml.api.incident_context.query_instant")
    def test_includes_recent_logs(self, mock_query, mock_logs):
        mock_query.return_value = [{"value": [1792600000, "1"]}]
        mock_logs.return_value = [
            {
                "timestamp": "1792692061002207040",
                "message": "system started",
                "signature": "system started",
            }
        ]

        context = collect_anomaly_context()

        self.assertEqual(context["logs"]["status"], "available")
        self.assertEqual(len(context["logs"]["entries"]), 1)
        self.assertEqual(
            context["logs"]["entries"][0]["message"],
            "system started",
        )
        mock_logs.assert_called_once_with(limit=20)

    @patch("ml.api.incident_context.query_recent_logs")
    @patch("ml.api.incident_context.query_instant")
    def test_loki_failure_does_not_break_metrics(
        self, mock_query, mock_logs
    ):
        mock_query.return_value = [{"value": [1792600000, "1"]}]
        mock_logs.side_effect = LokiError("Loki unavailable")

        context = collect_anomaly_context()

        self.assertEqual(context["metrics"]["anomaly_score"]["value"], 1.0)
        self.assertEqual(
            context["logs"],
            {"status": "unavailable", "entries": []},
        )

    @patch("ml.api.incident_context.list_recent_incidents")
    @patch("ml.api.incident_context.connect")
    @patch("ml.api.incident_context.query_recent_logs", return_value=[])
    @patch("ml.api.incident_context.query_instant")
    def test_includes_recent_incidents(
        self, mock_query, mock_logs, mock_connect, mock_list
    ):
        timestamp = datetime(2026, 10, 22, tzinfo=timezone.utc)
        mock_query.return_value = [{"value": [1792600000, "1"]}]
        mock_list.return_value = [
            {
                "id": "incident-1",
                "title": "High CPU usage",
                "opened_at": timestamp,
            }
        ]

        context = collect_anomaly_context()

        self.assertEqual(context["incidents"]["status"], "available")
        self.assertEqual(
            context["incidents"]["entries"],
            [
                {
                    "id": "incident-1",
                    "title": "High CPU usage",
                    "opened_at": timestamp.isoformat(),
                }
            ],
        )
        mock_list.assert_called_once_with(mock_connect.return_value, limit=20)
        mock_connect.return_value.close.assert_called_once()

    @patch("ml.api.incident_context.connect", side_effect=OSError("DB unavailable"))
    @patch("ml.api.incident_context.query_recent_logs", return_value=[])
    @patch("ml.api.incident_context.query_instant")
    def test_database_failure_does_not_break_metrics(
        self, mock_query, mock_logs, mock_connect
    ):
        mock_query.return_value = [{"value": [1792600000, "1"]}]

        context = collect_anomaly_context()

        self.assertEqual(context["metrics"]["anomaly_score"]["value"], 1.0)
        self.assertEqual(
            context["incidents"],
            {"status": "unavailable", "entries": []},
        )




if __name__ == "__main__":
    unittest.main()
