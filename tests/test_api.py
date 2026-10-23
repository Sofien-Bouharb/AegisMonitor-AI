"""Tests for the P20 correlation API."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import redis
from fastapi.testclient import TestClient

from ml.api.app import app
from ml.api.ollama_client import OllamaError
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


class OllamaApiTests(unittest.TestCase):
    @patch("ml.api.app.generate_text")
    def test_ai_generate_returns_model_output(self, mock_generate):
        mock_generate.return_value = "Check CPU and memory metrics."

        response = client.post(
            "/api/v1/ai/generate",
            json={"prompt": "Analyze these metrics."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"model_output": "Check CPU and memory metrics."},
        )
        mock_generate.assert_called_once_with("Analyze these metrics.")

    @patch("ml.api.app.generate_text")
    def test_ai_generate_returns_503_when_ollama_fails(self, mock_generate):
        from ml.api.ollama_client import OllamaError

        mock_generate.side_effect = OllamaError("connection refused")

        response = client.post(
            "/api/v1/ai/generate",
            json={"prompt": "Analyze these metrics."},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Local AI generation is temporarily unavailable.",
        )

    def test_ai_generate_rejects_blank_prompt(self):
        response = client.post(
            "/api/v1/ai/generate",
            json={"prompt": "   "},
        )

        self.assertEqual(response.status_code, 422)

    def test_ai_generate_rejects_unknown_fields(self):
        response = client.post(
            "/api/v1/ai/generate",
            json={"prompt": "Analyze metrics.", "system_override": True},
        )

        self.assertEqual(response.status_code, 422)


    @patch("ml.api.app.save_ai_analysis", return_value="00000000-0000-0000-0000-000000000010")
    @patch("ml.api.app.connect")
    @patch("ml.api.app.generate_text")
    @patch("ml.api.app.collect_anomaly_context")
    def test_ai_analyze_returns_analysis_and_context(
        self, mock_context, mock_generate, mock_connect, mock_save_analysis
    ):
        context = {
            "source": "prometheus",
            "metrics": {
                "anomaly_candidate": {"status": "available", "value": 1.0}
            },
            "logs": {"status": "unavailable", "entries": []},
            "incidents": {"status": "available", "entries": []},
        }
        mock_context.return_value = context
        mock_generate.return_value = (
            "An anomaly candidate was detected; this is not a confirmed incident."
        )

        response = client.post("/api/v1/ai/analyze")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "analysis_id": "00000000-0000-0000-0000-000000000010",
                "analysis": (
                    "An anomaly candidate was detected; "
                    "this is not a confirmed incident."
                ),
                "context": context,
            },
        )
        mock_context.assert_called_once_with()
        mock_save_analysis.assert_called_once_with(
            mock_connect.return_value,
            analysis=(
                "An anomaly candidate was detected; "
                "this is not a confirmed incident."
            ),
            context=context,
        )
        mock_connect.return_value.close.assert_called_once_with()
        prompt = mock_generate.call_args.args[0]
        self.assertIn('"anomaly_candidate"', prompt)
        self.assertIn("not a confirmed incident", prompt)
        self.assertIn("untrusted evidence", prompt)

    @patch("ml.api.app.collect_anomaly_context")
    def test_ai_analyze_returns_503_when_prometheus_fails(
        self, mock_context
    ):
        mock_context.side_effect = PrometheusError("Prometheus unavailable")

        response = client.post("/api/v1/ai/analyze")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Prometheus metrics are temporarily unavailable.",
        )

    @patch("ml.api.app.generate_text")
    @patch("ml.api.app.collect_anomaly_context")
    def test_ai_analyze_returns_503_when_ollama_fails(
        self, mock_context, mock_generate
    ):
        mock_context.return_value = {
            "source": "prometheus",
            "metrics": {},
            "logs": {"status": "unavailable", "entries": []},
            "incidents": {"status": "unavailable", "entries": []},
        }
        mock_generate.side_effect = OllamaError("connection refused")

        response = client.post("/api/v1/ai/analyze")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Local AI generation is temporarily unavailable.",
        )


class AIFeedbackApiTests(unittest.TestCase):
    analysis_id = "00000000-0000-0000-0000-000000000010"

    @patch("ml.api.app.save_ai_feedback", return_value="00000000-0000-0000-0000-000000000011")
    @patch("ml.api.app.connect")
    def test_saves_feedback(self, mock_connect, mock_save_feedback):
        response = client.post(
            "/api/v1/ai/feedback",
            json={
                "analysis_id": self.analysis_id,
                "verdict": "helpful",
                "comment": "The explanation matches the evidence.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "feedback_id": "00000000-0000-0000-0000-000000000011",
                "status": "saved",
            },
        )
        mock_save_feedback.assert_called_once_with(
            mock_connect.return_value,
            analysis_id=self.analysis_id,
            verdict="helpful",
            comment="The explanation matches the evidence.",
        )
        mock_connect.return_value.close.assert_called_once_with()

    def test_rejects_invalid_verdict(self):
        response = client.post(
            "/api/v1/ai/feedback",
            json={"analysis_id": self.analysis_id, "verdict": "maybe"},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_invalid_analysis_id(self):
        response = client.post(
            "/api/v1/ai/feedback",
            json={"analysis_id": "not-a-uuid", "verdict": "correct"},
        )
        self.assertEqual(response.status_code, 422)

    @patch("ml.api.app.save_ai_feedback")
    @patch("ml.api.app.connect")
    def test_returns_404_when_analysis_does_not_exist(
        self, mock_connect, mock_save_feedback
    ):
        import psycopg

        mock_save_feedback.side_effect = psycopg.errors.ForeignKeyViolation(
            "analysis not found"
        )
        response = client.post(
            "/api/v1/ai/feedback",
            json={"analysis_id": self.analysis_id, "verdict": "correct"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "The requested AI analysis was not found.",
        )
        mock_connect.return_value.close.assert_called_once_with()

    @patch("ml.api.app.connect", side_effect=Exception("connection failed"))
    def test_returns_503_when_feedback_database_connection_fails(
        self, mock_connect
    ):
        import psycopg

        mock_connect.side_effect = psycopg.OperationalError("connection failed")
        response = client.post(
            "/api/v1/ai/feedback",
            json={"analysis_id": self.analysis_id, "verdict": "incorrect"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "AI feedback persistence is temporarily unavailable.",
        )
