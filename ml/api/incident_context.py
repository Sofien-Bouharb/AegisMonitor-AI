
"""Build a structured snapshot of anomaly-exporter and log evidence."""

from typing import Any

from ml.api.loki_client import LokiError, query_recent_logs
from ml.api.prometheus_client import PrometheusError, query_instant
import psycopg

from ml.database.connection import connect
from ml.database.repository import list_recent_incidents

from datetime import datetime


CONTEXT_METRICS = {
    "anomaly_score": "aegismonitor_anomaly_score",
    "anomaly_candidate": "aegismonitor_anomaly_candidate",
    "evaluation_success": "aegismonitor_exporter_evaluation_success",
    "last_success_timestamp_seconds": (
        "aegismonitor_exporter_last_success_timestamp_seconds"
    ),
}


def _read_metric(metric_name: str) -> dict[str, Any]:
    """Return one metric's value, preserving missing data as unavailable."""
    results = query_instant(metric_name)
    if not results:
        return {"status": "unavailable", "value": None}
    if len(results) != 1:
        raise PrometheusError(
            f"Prometheus returned multiple series for {metric_name}."
        )

    sample = results[0].get("value")
    if not isinstance(sample, list) or len(sample) != 2:
        raise PrometheusError(
            f"Prometheus returned an invalid sample for {metric_name}."
        )

    try:
        value = float(sample[1])
    except (TypeError, ValueError) as exc:
        raise PrometheusError(
            f"Prometheus returned a non-numeric sample for {metric_name}."
        ) from exc

    return {"status": "available", "value": value}


def _read_logs() -> dict[str, Any]:
    """Return recent logs or explicitly mark log evidence unavailable."""
    try:
        entries = query_recent_logs(limit=20)
    except LokiError:
        return {"status": "unavailable", "entries": []}

    return {"status": "available", "entries": entries}


def _read_incidents() -> dict[str, Any]:
    """Return recent persisted incidents or mark database evidence unavailable."""
    conn = None
    try:
        conn = connect()
        incidents = list_recent_incidents(conn, limit=20)
    except (psycopg.Error, OSError):
        return {"status": "unavailable", "entries": []}
    finally:
        if conn is not None:
            conn.close()

    return {
        "status": "available",
        "entries": [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in incident.items()
            }
            for incident in incidents
        ],
    }




def collect_anomaly_context() -> dict[str, Any]:
    """Collect anomaly metrics and bounded recent log evidence."""
    metrics = {
        key: _read_metric(metric_name)
        for key, metric_name in CONTEXT_METRICS.items()
    }
    return {
        "source": "prometheus",
        "metrics": metrics,
        "logs": _read_logs(),
        "incidents": _read_incidents(),
    }
