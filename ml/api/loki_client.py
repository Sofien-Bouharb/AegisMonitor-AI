
"""Small, bounded Loki log-query client for incident context."""

import json
import os
from typing import Any

import httpx


DEFAULT_LOKI_URL = "http://localhost:3100"
REQUEST_TIMEOUT_SECONDS = 5.0
MAX_ENTRIES = 100
DEFAULT_SINCE = "15m"


class LokiError(RuntimeError):
    """Raised when Loki cannot provide valid log results."""


def query_recent_logs(
    *,
    base_url: str | None = None,
    since: str = DEFAULT_SINCE,
    limit: int = 20,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Return a bounded list of recent logs with only relevant fields."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ENTRIES:
        raise ValueError(f"limit must be between 1 and {MAX_ENTRIES}")
    if since != DEFAULT_SINCE:
        raise ValueError(f"since must be {DEFAULT_SINCE!r}")

    url = (base_url or os.getenv("LOKI_URL", DEFAULT_LOKI_URL)).rstrip("/")
    try:
        response = httpx.get(
            f"{url}/loki/api/v1/query_range",
            params={
                "query": '{job="fluent-bit",source="systemd"}',
                "limit": limit,
                "since": since,
                "direction": "backward",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LokiError("Loki query failed.") from exc

    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise LokiError("Loki returned an unsuccessful response.")

    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "streams":
        raise LokiError("Loki response is not a valid stream result.")

    streams = data.get("result")
    if not isinstance(streams, list):
        raise LokiError("Loki response has an invalid result format.")

    logs: list[dict[str, Any]] = []
    for stream in streams:
        if not isinstance(stream, dict):
            raise LokiError("Loki returned an invalid stream.")

        values = stream.get("values")
        if not isinstance(values, list):
            raise LokiError("Loki stream has invalid values.")

        for entry in values:
            if not isinstance(entry, list) or len(entry) != 2:
                raise LokiError("Loki returned an invalid log entry.")

            timestamp, line = entry
            if not isinstance(timestamp, str) or not isinstance(line, str):
                raise LokiError("Loki returned an invalid log entry.")

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                record = {"MESSAGE": line}

            if not isinstance(record, dict):
                raise LokiError("Loki log payload must be a JSON object.")

            message = record.get("MESSAGE")
            signature = record.get("signature")
            logs.append(
                {
                    "timestamp": timestamp,
                    "message": message if isinstance(message, str) else line,
                    "signature": signature if isinstance(signature, str) else None,
                }
            )

            if len(logs) >= limit:
                return logs

    return logs
