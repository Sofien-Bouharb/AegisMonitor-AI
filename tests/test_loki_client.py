
"""Tests for the bounded Loki log-query client."""

import unittest
from unittest.mock import Mock, patch

import httpx

from ml.api.loki_client import (
    DEFAULT_LOKI_URL,
    LokiError,
    query_recent_logs,
)


class LokiClientTests(unittest.TestCase):
    @patch("ml.api.loki_client.httpx.get")
    def test_parses_recent_logs_and_limits_returned_fields(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [
                        {
                            "stream": {
                                "job": "fluent-bit",
                                "source": "systemd",
                            },
                            "values": [
                                [
                                    "1792692061002207040",
                                    '{"MESSAGE":"system started",'
                                    '"signature":"system started",'
                                    '"_PID":"123"}',
                                ],
                                [
                                    "1792692061001625061",
                                    '{"MESSAGE":"cron finished"}',
                                ],
                            ],
                        }
                    ],
                },
            },
        )

        logs = query_recent_logs(base_url="http://loki:3100", limit=2)

        self.assertEqual(len(logs), 2)
        self.assertEqual(
            logs[0],
            {
                "timestamp": "1792692061002207040",
                "message": "system started",
                "signature": "system started",
            },
        )
        self.assertIsNone(logs[1]["signature"])
        self.assertNotIn("_PID", logs[0])
        mock_get.assert_called_once_with(
            "http://loki:3100/loki/api/v1/query_range",
            params={
                "query": '{job="fluent-bit",source="systemd"}',
                "limit": 2,
                "since": "15m",
                "direction": "backward",
            },
            timeout=5.0,
        )

    @patch("ml.api.loki_client.httpx.get")
    def test_uses_environment_url(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"resultType": "streams", "result": []},
            },
        )

        with patch.dict("os.environ", {"LOKI_URL": "http://loki:3100"}):
            self.assertEqual(query_recent_logs(), [])

        self.assertEqual(
            mock_get.call_args.args[0],
            "http://loki:3100/loki/api/v1/query_range",
        )

    @patch("ml.api.loki_client.httpx.get")
    def test_default_url_is_local_loki(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"resultType": "streams", "result": []},
            },
        )

        with patch.dict("os.environ", {}, clear=True):
            query_recent_logs()

        self.assertEqual(
            mock_get.call_args.args[0],
            f"{DEFAULT_LOKI_URL}/loki/api/v1/query_range",
        )

    def test_rejects_invalid_limits(self):
        for limit in (0, -1, 101, True, 1.5):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    query_recent_logs(limit=limit)

    @patch("ml.api.loki_client.httpx.get")
    def test_http_failure_raises_loki_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        with self.assertRaises(LokiError):
            query_recent_logs()

    @patch("ml.api.loki_client.httpx.get")
    def test_unsuccessful_response_raises_loki_error(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"status": "error"},
        )

        with self.assertRaises(LokiError):
            query_recent_logs()

    @patch("ml.api.loki_client.httpx.get")
    def test_rejects_malformed_stream_entry(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [{"values": [["timestamp"]]}],
                },
            },
        )

        with self.assertRaises(LokiError):
            query_recent_logs()

    @patch("ml.api.loki_client.httpx.get")
    def test_falls_back_for_plain_text_log_lines(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [
                        {"values": [["123", "plain text log line"]]}
                    ],
                },
            },
        )

        logs = query_recent_logs()

        self.assertEqual(
            logs,
            [
                {
                    "timestamp": "123",
                    "message": "plain text log line",
                    "signature": None,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
