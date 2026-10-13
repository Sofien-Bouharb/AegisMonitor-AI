#!/usr/bin/env python3
"""Collect live AegisMonitor host metrics from the Prometheus HTTP API."""

import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PROMETHEUS_URL = "http://localhost:9090/api/v1/query"
SAMPLE_INTERVAL_SECONDS = 15
OUTPUT_FILE = Path("data/telemetry/live_metrics.csv")

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

FIELDNAMES = ["timestamp", *QUERIES.keys()]


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
    if not value == value or abs(value) == float("inf"):
        raise ValueError(f"Metric is not finite: {value}")

    return value


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = OUTPUT_FILE.exists() and OUTPUT_FILE.stat().st_size > 0

    with requests.Session() as session, OUTPUT_FILE.open(
        "a", newline="", encoding="utf-8"
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)

        if not file_exists:
            writer.writeheader()
            csv_file.flush()

        print(f"Prometheus: {PROMETHEUS_URL}")
        print(f"Output:     {OUTPUT_FILE}")
        print(f"Interval:   {SAMPLE_INTERVAL_SECONDS}s")
        print("Collecting metrics; press Ctrl+C to stop.")

        try:
            while True:
                started = time.monotonic()
                timestamp = datetime.now(timezone.utc).isoformat()
                sample = {"timestamp": timestamp}

                try:
                    for name, query in QUERIES.items():
                        sample[name] = query_metric(session, query)

                    writer.writerow(sample)
                    csv_file.flush()
                    print(
                        f"{timestamp} | "
                        + " | ".join(
                            f"{name}={sample[name]:.3f}"
                            for name in QUERIES
                        )
                    )
                except (requests.RequestException, ValueError, RuntimeError) as exc:
                    print(f"{timestamp} | sample skipped: {exc}")

                elapsed = time.monotonic() - started
                time.sleep(max(0, SAMPLE_INTERVAL_SECONDS - elapsed))

        except KeyboardInterrupt:
            print("\nCollection stopped.")


if __name__ == "__main__":
    main()
