#!/usr/bin/env python3
"""Expose live Isolation Forest scores and supporting metrics to Prometheus."""

import json
import logging
import math
import os
import time
from pathlib import Path

import joblib
import numpy as np
import requests
from prometheus_client import Counter, Gauge, start_http_server

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL", "http://prometheus:9090/api/v1/query"
)
MODEL_PATH = Path(os.getenv("MODEL_PATH", "/models/model.joblib"))
METADATA_PATH = Path(os.getenv("METADATA_PATH", "/models/metadata.json"))
SCRAPE_PORT = int(os.getenv("EXPORTER_PORT", "9101"))
INTERVAL_SECONDS = int(os.getenv("EVALUATION_INTERVAL_SECONDS", "15"))

FEATURES = [
    "cpu_usage_pct",
    "memory_usage_pct",
    "disk_write_bytes_per_second",
    "network_receive_bytes_per_second",
    "load1",
]

QUERIES = {
    "cpu_usage_pct": (
        '100 * (1 - avg by (instance) '
        '(rate(node_cpu_seconds_total{mode="idle"}[5m])))'
    ),
    "memory_usage_pct": (
        "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)"
    ),
    "disk_write_bytes_per_second": (
        "sum(rate(node_disk_written_bytes_total[5m]))"
    ),
    "network_receive_bytes_per_second": (
        'sum(rate(node_network_receive_bytes_total{device!="lo"}[5m]))'
    ),
    "load1": "node_load1",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

ANOMALY_SCORE = Gauge(
    "aegismonitor_anomaly_score",
    "Isolation Forest score; lower values are more anomalous.",
)
ANOMALY_CANDIDATE = Gauge(
    "aegismonitor_anomaly_candidate",
    "1 when the score is below the saved calibration threshold, otherwise 0.",
)
EVALUATION_TIMESTAMP = Gauge(
    "aegismonitor_anomaly_evaluation_timestamp_seconds",
    "Unix timestamp of the latest successful model evaluation.",
)
MODEL_VERSION = Gauge(
    "aegismonitor_model_info",
    "Loaded AegisMonitor model version.",
    ["version"],
)
LAST_SUCCESS = Gauge(
    "aegismonitor_exporter_last_success_timestamp_seconds",
    "Unix timestamp of the latest successful collection and evaluation.",
)
EVALUATION_SUCCESS = Gauge(
    "aegismonitor_exporter_evaluation_success",
    "1 if the latest evaluation cycle succeeded, otherwise 0.",
)
ERRORS = Counter(
    "aegismonitor_exporter_errors_total",
    "Number of failed collection or evaluation cycles.",
)

SUPPORTING_METRICS = {
    feature: Gauge(
        f"aegismonitor_{feature}",
        f"Latest input value for Isolation Forest feature {feature}.",
    )
    for feature in FEATURES
}


def query_metric(session, query):
    response = session.get(
        PROMETHEUS_URL,
        params={"query": query},
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")

    results = payload["data"]["result"]
    if len(results) != 1:
        raise ValueError(f"Expected one result, got {len(results)}")

    value = float(results[0]["value"][1])
    if not math.isfinite(value):
        raise ValueError(f"Metric is not finite: {value}")

    return value


def main():
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if metadata.get("features") != FEATURES:
        raise ValueError("Model metadata feature order does not match.")

    threshold = float(metadata["anomaly_threshold_on_score_samples"])
    model = joblib.load(MODEL_PATH)
    MODEL_VERSION.labels(version=str(metadata.get("version", "unknown"))).set(1)

    start_http_server(SCRAPE_PORT, addr="0.0.0.0")
    logging.info("Exporter listening on port %s", SCRAPE_PORT)
    logging.info("Prometheus query endpoint: %s", PROMETHEUS_URL)
    logging.info("Loaded model version %s", metadata.get("version"))
    logging.info("Using saved anomaly threshold %.12f", threshold)

    with requests.Session() as session:
        while True:
            started = time.monotonic()
            try:
                sample = {
                    name: query_metric(session, QUERIES[name])
                    for name in FEATURES
                }
                values = np.asarray(
                    [[sample[name] for name in FEATURES]],
                    dtype=float,
                )
                if not np.isfinite(values).all():
                    raise ValueError("Input features contain non-finite values.")

                score = float(model.score_samples(values)[0])
                if not math.isfinite(score):
                    raise ValueError(f"Model score is not finite: {score}")

                is_candidate = score < threshold
                now = time.time()

                for name, value in sample.items():
                    SUPPORTING_METRICS[name].set(value)

                ANOMALY_SCORE.set(score)
                ANOMALY_CANDIDATE.set(1 if is_candidate else 0)
                EVALUATION_TIMESTAMP.set(now)
                LAST_SUCCESS.set(now)
                EVALUATION_SUCCESS.set(1)

                logging.info(
                    "score=%.6f candidate=%s cpu=%.2f%% memory=%.2f%% "
                    "disk_write=%.2f B/s network_receive=%.2f B/s load1=%.2f",
                    score,
                    is_candidate,
                    sample["cpu_usage_pct"],
                    sample["memory_usage_pct"],
                    sample["disk_write_bytes_per_second"],
                    sample["network_receive_bytes_per_second"],
                    sample["load1"],
                )
            except (
                requests.RequestException,
                ValueError,
                RuntimeError,
                KeyError,
            ) as exc:
                ERRORS.inc()
                EVALUATION_SUCCESS.set(0)
                logging.error("Evaluation cycle failed: %s", exc)

            elapsed = time.monotonic() - started
            time.sleep(max(0, INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    main()
