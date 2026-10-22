"""Tests for the Prometheus instant-query client."""

import unittest
from unittest.mock import Mock, patch

import httpx

from ml.api.prometheus_client import (
    DEFAULT_PROMETHEUS_URL,
    PrometheusError,
    query_instant,
)


class PrometheusClientTests(unittest.TestCase):
    @patch("ml.api.prometheus_client.httpx.get")
    def test_returns_vector_result_and_uses_configured_url(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {"job": "node-exporter"},
                            "value": [1792600000, "42.5"],
                        }
                    ],
                },
            },
        )

        result = query_instant(
            "up",
            base_url="http://prometheus:9090/",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["metric"]["job"], "node-exporter")
        mock_get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query",
            params={"query": "up"},
            timeout=5.0,
        )

    @patch("ml.api.prometheus_client.httpx.get")
    def test_uses_environment_url(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )

        with patch.dict("os.environ", {"PROMETHEUS_URL": "http://prom:9090"}):
            self.assertEqual(query_instant("up"), [])

        self.assertEqual(
            mock_get.call_args.args[0],
            "http://prom:9090/api/v1/query",
        )

    def test_rejects_blank_query(self):
        with self.assertRaises(ValueError):
            query_instant("  ")

    @patch("ml.api.prometheus_client.httpx.get")
    def test_http_failure_raises_prometheus_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        with self.assertRaises(PrometheusError):
            query_instant("up")

    @patch("ml.api.prometheus_client.httpx.get")
    def test_unsuccessful_prometheus_response_raises_error(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"status": "error", "error": "bad query"},
        )

        with self.assertRaises(PrometheusError):
            query_instant("up")

    @patch("ml.api.prometheus_client.httpx.get")
    def test_malformed_response_raises_error(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"status": "success", "data": []},
        )

        with self.assertRaises(PrometheusError):
            query_instant("up")

    @patch("ml.api.prometheus_client.httpx.get")
    def test_rejects_scalar_response(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"resultType": "scalar", "result": [1792600000, "1"]},
            },
        )

        with self.assertRaises(PrometheusError):
            query_instant("up")

    @patch("ml.api.prometheus_client.httpx.get")
    def test_rejects_malformed_vector_entries(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"resultType": "vector", "result": ["invalid"]},
            },
        )

        with self.assertRaises(PrometheusError):
            query_instant("up")

    @patch("ml.api.prometheus_client.httpx.get")
    def test_default_url_is_local_prometheus(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )

        with patch.dict("os.environ", {}, clear=True):
            query_instant("up")

        self.assertEqual(
            mock_get.call_args.args[0],
            f"{DEFAULT_PROMETHEUS_URL}/api/v1/query",
        )


if __name__ == "__main__":
    unittest.main()
