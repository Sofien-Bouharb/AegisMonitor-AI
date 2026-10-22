"""Small HTTP client for Prometheus instant vector queries."""

import os
from typing import Any

import httpx


DEFAULT_PROMETHEUS_URL = "http://localhost:9090"
REQUEST_TIMEOUT_SECONDS = 5.0


class PrometheusError(RuntimeError):
    """Raised when Prometheus cannot provide a valid query response."""


def query_instant(
    query: str,
    *,
    base_url: str | None = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Execute an instant vector query and return its result entries."""
    if not query.strip():
        raise ValueError("PromQL query cannot be blank")

    url = (base_url or os.getenv("PROMETHEUS_URL", DEFAULT_PROMETHEUS_URL)).rstrip("/")
    try:
        response = httpx.get(
            f"{url}/api/v1/query",
            params={"query": query},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PrometheusError("Prometheus query failed.") from exc

    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise PrometheusError("Prometheus returned an unsuccessful response.")

    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "vector":
        raise PrometheusError("Prometheus response is not a valid instant vector.")

    result = data.get("result")
    if not isinstance(result, list) or any(
        not isinstance(item, dict) for item in result
    ):
        raise PrometheusError("Prometheus response has an invalid result format.")

    return result
