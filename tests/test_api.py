"""Tests for the P20 correlation API."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import redis
from fastapi.testclient import TestClient

from ml.api.app import app
from ml.api.prometheus_client import PrometheusError

client = TestClient(app)


class CorrelationApiTests(unittest.TestCase):
    def setUp(self):
        self.timestamp = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
        self.redis_client = Mock()
        self.stored_signals = []

        self.create_client_patch = patch(
            "ml.api.app.create_client",
            return_value=self.redis_client,
        )
        self.store_signal_patch = patch(
            "ml.api.app.store_signal",
            side_effect=self.fake_store_signal,
        )
        self.window_patch = patch(
            "ml.api.app.correlation_window_seconds",
            return_value=300,
        )

        self.create_client_patch.start()
        self.store_signal_patch.start()
        self.window_patch.start()
        self.addCleanup(self.create_client_patch.stop)
        self.addCleanup(self.store_signal_patch.stop)
        self.addCleanup(self.window_patch.stop)

    def fake_store_signal(self, client, signal, window_seconds=300, now=None):
        """Simulate a per-host Redis correlation window."""
        self.stored_signals.append(signal)
        return [
            item
            for item in self.stored_signals
            if item.host == signal.host
            and abs((signal.occurred_at - item.occurred_at).total_seconds())
            <= window_seconds
        ]

    def signal(self, signal_type, name, **overrides):
        value = {
            "signal_type": signal_type,
            "name": name,
            "occurred_at": self.timestamp.isoformat(),
            "severity": "warning",
            "host": "localhost",
            "source": "test",
        }
        value.update(overrides)
        return value

    def test_health_endpoint(self):
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("ml.api.app.collect_anomaly_context")
    def test_incident_context_metrics_endpoint(self, mock_context):
        mock_context.return_value = {
            "source": "prometheus",
            "metrics": {
                "anomaly_candidate": {
                    "status": "available",
                    "value": 1.0,
                }
            },
        }

        response = client.get("/api/v1/context/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_context.return_value)

    @patch("ml.api.app.collect_anomaly_context")
    def test_incident_context_metrics_returns_503_on_prometheus_error(
        self, mock_context
    ):
        mock_context.side_effect = PrometheusError("connection failed")

        response = client.get("/api/v1/context/metrics")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Prometheus metrics are temporarily unavailable.",
        )

    def test_correlates_alert_and_anomaly(self):
        response = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal("anomaly", "CPU anomaly candidate"),
                    self.signal(
                        "alert",
                        "HighCPUUsage",
                        occurred_at=(
                            self.timestamp + timedelta(minutes=1)
                        ).isoformat(),
                    ),
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["incident_count"], 1)
        self.assertEqual(len(body["incidents"][0]["relationships"]), 2)
        self.redis_client.close.assert_called_once()

    def test_correlates_signals_for_non_default_host(self):
        host = "custom-test-host"
        response = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal(
                        "anomaly",
                        "CPU anomaly candidate",
                        host=host,
                    ),
                    self.signal(
                        "alert",
                        "HighCPUUsage",
                        host=host,
                    ),
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["incident_count"], 1)
        self.assertEqual(body["incidents"][0]["host"], host)
        self.assertEqual(len(body["incidents"][0]["relationships"]), 2)

    def test_correlates_signals_across_separate_requests(self):
        first = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal("anomaly", "CPU anomaly candidate"),
                ]
            },
        )
        second = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal(
                        "alert",
                        "HighCPUUsage",
                        occurred_at=(
                            self.timestamp + timedelta(minutes=1)
                        ).isoformat(),
                    ),
                ]
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["incident_count"], 0)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["incident_count"], 1)
        self.assertEqual(
            len(second.json()["incidents"][0]["relationships"]),
            2,
        )

    def test_anomaly_candidate_alone_does_not_create_incident(self):
        response = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal("anomaly", "CPU anomaly candidate")
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"incident_count": 0, "incidents": []},
        )

    def test_empty_signals_do_not_connect_to_redis(self):
        response = client.post(
            "/api/v1/correlate",
            json={"signals": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"incident_count": 0, "incidents": []},
        )
        self.create_client_patch.stop()
        self.create_client_patch = patch(
            "ml.api.app.create_client",
            side_effect=AssertionError("Redis should not be accessed"),
        )
        self.create_client_patch.start()

        response = client.post(
            "/api/v1/correlate",
            json={"signals": []},
        )
        self.assertEqual(response.status_code, 200)

    def test_redis_failure_returns_503(self):
        with patch(
            "ml.api.app.store_signal",
            side_effect=redis.ConnectionError("Redis unavailable"),
        ):
            response = client.post(
                "/api/v1/correlate",
                json={
                    "signals": [
                        self.signal("alert", "HighCPUUsage")
                    ]
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Correlation state is temporarily unavailable.",
        )
        self.redis_client.close.assert_called_once()

    def test_rejects_unknown_signal_type(self):
        response = client.post(
            "/api/v1/correlate",
            json={"signals": [self.signal("unknown", "Invalid signal")]},
        )

        self.assertEqual(response.status_code, 422)

    def test_rejects_timestamp_without_timezone(self):
        response = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal(
                        "alert",
                        "HighCPUUsage",
                        occurred_at="2026-10-21T12:00:00",
                    )
                ]
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_rejects_unexpected_fields(self):
        response = client.post(
            "/api/v1/correlate",
            json={
                "signals": [
                    self.signal(
                        "alert",
                        "HighCPUUsage",
                        unexpected="not allowed",
                    )
                ]
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_engine_exception_is_not_silently_swallowed(self):
        with patch(
            "ml.api.app.CorrelationEngine.correlate",
            side_effect=RuntimeError("correlation failed"),
        ):
            with self.assertRaises(RuntimeError):
                client.post(
                    "/api/v1/correlate",
                    json={
                        "signals": [
                            self.signal("alert", "HighCPUUsage")
                        ]
                    },
                )


if __name__ == "__main__":
    unittest.main()
