# AegisMonitor AI — P21 Technical Handoff Report

**Report date:** 2026-10-22  
**Project:** AegisMonitor AI  
**Repository:** `~/Projects/AegisMonitor-AI`  
**Branch:** `main`  
**Remote:** `origin/main`  
**Previous confirmed commit:** `199b6d3` — `worked on p20: fastApi and completed it`  
**Project type:** Personal portfolio project, not an internship  
**Runtime environment:** Fedora Linux, Docker Compose, local/self-hosted infrastructure

---

## 1. Objective

P21 introduces data interfaces that allow the FastAPI correlation service to retrieve operational context from the existing monitoring stack.

The objective is to make a bounded, structured context available from:

- Prometheus anomaly and exporter metrics.
- Loki recent log entries.
- PostgreSQL historical incidents.

This provides a data foundation for later local LLM integration. P21 does not itself implement AI-generated incident analysis, automated remediation, or a complete incident lifecycle.

## 2. Architecture and responsibilities

### FastAPI

The existing `correlation-api` service exposes the context endpoint:

`GET /api/v1/context/metrics`

The endpoint returns a structured JSON response containing metric values and availability, recent logs, and recent incidents.

The endpoint is a data-retrieval interface. It does not decide whether an anomaly is a confirmed incident and does not generate an LLM assessment.

The existing `/health` and `POST /api/v1/correlate` endpoints remain in place.

### Prometheus

Prometheus provides current anomaly-exporter metrics through its HTTP query API.

The P21 client retrieves four metrics:

- `aegismonitor_anomaly_score`
- `aegismonitor_anomaly_candidate`
- `aegismonitor_exporter_evaluation_success`
- `aegismonitor_exporter_last_success_timestamp_seconds`

The interface distinguishes an available metric value from an unavailable metric. A missing metric is not silently converted to zero.

### Loki

Loki provides recent log context through its range-query API.

The current client uses a fixed selector:

`{job="fluent-bit",source="systemd"}`

The query is limited to the most recent 15 minutes and a maximum of 20 entries by default. The client returns timestamps, messages, and signature information where available.

This is a bounded context retrieval mechanism, not a general-purpose log search API.

### PostgreSQL

PostgreSQL remains the durable source of truth for persisted incidents.

P21 adds a repository function to retrieve a bounded list of recent incidents. It does not automatically persist every anomaly candidate or every result returned by the correlation API.

An empty incident list is valid when no incidents have been persisted.

### Redis and the correlation engine

P21 does not replace the P17 correlation engine or change the P19 Redis scope.

Redis remains an ephemeral state store. PostgreSQL remains the durable persistence layer.

## 3. Implementation files

### New files

- `ml/api/prometheus_client.py`
- `ml/api/loki_client.py`
- `ml/api/incident_context.py`
- `tests/test_prometheus_client.py`
- `tests/test_loki_client.py`
- `tests/test_incident_context.py`

### Modified files

- `ml/api/app.py`
- `ml/database/repository.py`
- `docker-compose.yml`
- `tests/test_api.py`
- `tests/test_database_repository.py`

The final Git diff should be inspected before committing to confirm that only the intended P21 files and this report are included.

## 4. Prometheus client

Implementation:

`ml/api/prometheus_client.py`

The client exposes `query_instant(query, base_url=None, timeout=5.0)`.

It queries the Prometheus HTTP endpoint:

`/api/v1/query`

The base URL defaults to `PROMETHEUS_URL`, or `http://localhost:9090` when the environment variable is not set.

The client validates the query response and expects a successful vector result. Prometheus failures are represented by `PrometheusError`.

The collector converts metric values to floats and returns an explicit availability status for each metric. Missing metrics are represented as unavailable rather than being treated as a normal value of zero.

The client tests cover query behavior and error handling. Nine Prometheus-client tests were reported as passing.

## 5. Loki client

Implementation:

`ml/api/loki_client.py`

The client exposes:

`query_recent_logs(base_url=None, since="15m", limit=20, timeout=5.0)`

It queries:

`/loki/api/v1/query_range`

The base URL defaults to `LOKI_URL`, or `http://localhost:3100` when the environment variable is not set.

The current implementation:

- Uses a fixed Fluent Bit/systemd selector.
- Limits the requested time range to 15 minutes.
- Restricts the number of returned entries to 1–100.
- Defaults to returning at most 20 entries.
- Returns timestamps, messages, and signature information where available.
- Handles JSON and plain-text fallback responses.
- Raises `LokiError` when the query fails.

The context collector treats Loki failures as a degraded context source rather than failing the entire request.

Eight Loki-client tests were reported as passing.

## 6. Structured incident-context collector

Implementation:

`ml/api/incident_context.py`

The collector combines three data sources into a structured response.

### Metrics

The response includes the four P21 Prometheus metrics:

- Anomaly score.
- Anomaly-candidate indicator.
- Exporter evaluation success.
- Last successful exporter evaluation timestamp.

Each metric reports its availability and value. Unavailable metrics use a null value; they are not represented as zero.

Invalid metric values or ambiguous multiple-series results raise `PrometheusError`.

### Logs

The collector requests up to 20 recent log entries from Loki.

If Loki is unavailable, the logs section reports an unavailable status and an empty entry list. This allows the rest of the context to remain useful.

### Incidents

The collector connects to PostgreSQL and calls `list_recent_incidents()` with a limit of 20.

Database connection or operating-system failures degrade the incidents section to unavailable with an empty entry list. The database connection is closed after use.

Datetime fields are serialized as ISO-formatted strings for JSON compatibility.

### Response shape

The response has this top-level structure:

```json
{
  "source": "prometheus",
  "metrics": {},
  "logs": {
    "status": "available",
    "entries": []
  },
  "incidents": {
    "status": "available",
    "entries": []
  }
}
```
