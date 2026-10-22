# P16 — Build Anomaly Dashboard

## 1. Objective

The objective of P16 was to integrate the Isolation Forest anomaly detection system implemented in P15 into Grafana and provide a centralized dashboard for monitoring anomaly scores, detected anomaly candidates, affected hosts, anomalous periods, and supporting system telemetry.

The dashboard is intended to make the model's output interpretable and provide the observability foundation for the subsequent event, alert, and incident correlation milestones.

## 2. Implementation

### 2.1 Dashboard file

- **File:** `grafana/dashboards/anomaly-dashboard.json`
- **Dashboard title:** `AegisMonitor - Anomaly Dashboard`
- **Dashboard UID:** `aegis-anomaly-dashboard`
- **Dashboard type:** Grafana dashboard provisioned from a JSON file.

The dashboard contains 12 panels.

| # | Panel | Purpose |
|---|---|---|
| 1 | Current Anomaly Status | Displays the current anomaly candidate flag. |
| 2 | Isolation Forest Anomaly Score | Displays the model score and fixed detection threshold. |
| 3 | Evaluation Health | Shows the status of model evaluations. |
| 4 | Anomalous Periods | Helps visualize periods identified as anomalous. |
| 5 | Affected Hosts — Current Status | Displays the current anomaly status by host. |
| 6 | CPU Usage | Provides CPU context for interpreting anomaly scores. |
| 7 | Memory Usage | Provides memory utilization context. |
| 8 | Disk Write Throughput | Provides disk I/O context. |
| 9 | Network Receive Throughput | Provides network I/O context. |
| 10 | Load Average | Provides system load context. |
| 11 | Seconds Since Last Successful Evaluation | Helps identify stale evaluation results. |
| 12 | Exporter Errors | Monitors errors reported by the anomaly exporter. |

## 3. Technical Architecture

The P15 model is exposed to Prometheus through the anomaly exporter. Grafana queries Prometheus to visualize the model output and supporting telemetry.

The data flow is:

1. The anomaly exporter collects the five required system features.
2. It loads the existing P15 v2 Isolation Forest model and evaluates the current feature vector.
3. The exporter exposes the score, candidate flag, feature values, and evaluation health as Prometheus metrics.
4. Prometheus scrapes the exporter.
5. Grafana queries Prometheus and displays the results in the anomaly dashboard.

The exporter is located at:

`ml/anomaly_exporter/app.py`

The model and metadata files are:

- `models/p15_live_isolation_forest_v2.joblib`
- `models/p15_live_metadata_v2.json`

The exporter is scraped by Prometheus under the job name `anomaly-exporter`, using port `9101`. Its configured labels include `host="localhost"` and `env="local"`.

The monitoring stack uses Docker Compose's `dev` profile. Monitoring-stack commands should therefore include `--profile dev`.

## 4. Model and Detection Configuration

P16 uses the existing model produced in P15. The model was not retrained, and its detection threshold was not changed.

- **Model:** Isolation Forest v2
- **Fixed threshold:** `-0.670917882340376`
- **Decision rule:** a score strictly below the threshold is classified as an anomaly candidate.
- **Candidate condition:** `anomaly_score < -0.670917882340376`

A score equal to the threshold does not satisfy the candidate condition.

The dashboard visualizes model output; it does not independently train the model or calculate a different detection threshold.

### 4.1 Model hyperparameters

The P15 v2 model uses the following configuration:

| Hyperparameter | Value |
|---|---|
| `n_estimators` | `200` |
| `max_samples` | `"auto"` |
| `contamination` | `"auto"` |
| `random_state` | `42` |
| `n_jobs` | `-1` |
| `max_features` | `1.0` |
| `bootstrap` | `false` |

These values are documented here for continuity. They were not modified as part of P16.

### 4.2 Important model limitation

The model was trained using live telemetry collected during normal laptop use, but the dataset was not verified to be entirely anomaly-free. The calibration tail fraction is not a guarantee of the future false-positive rate, and the live dataset does not have ground-truth anomaly labels.

Consequently, the anomaly score should be interpreted as an unsupervised model output, not a calibrated probability that an incident is occurring.

## 5. Prometheus Metrics

The following metrics are relevant to the dashboard and future debugging.

### 5.1 Anomaly detection and evaluation

| Metric | Meaning |
|---|---|
| `aegismonitor_anomaly_score` | Isolation Forest anomaly score. |
| `aegismonitor_anomaly_candidate` | Current candidate flag; `1` means candidate and `0` means no candidate. |
| `aegismonitor_anomaly_evaluation_timestamp_seconds` | Timestamp associated with an evaluation. |
| `aegismonitor_model_info` | Model-identification information exposed as a metric. |
| `aegismonitor_exporter_last_success_timestamp_seconds` | Timestamp of the last successful evaluation. |
| `aegismonitor_exporter_evaluation_success` | Indicates whether the latest evaluation succeeded. |
| `aegismonitor_exporter_errors_total` | Exporter error counter. |

The exporter also exposes standard Python, process, `up`, and scrape-related metrics.

**Important troubleshooting note:** if an evaluation fails, the score and candidate flag can remain stale. The evaluation-success metric becomes `0`, while the last-success timestamp remains unchanged. Therefore, a displayed candidate flag must be interpreted alongside evaluation health and metric freshness.

The error counter is cumulative. A nonzero historical value does not, by itself, prove that the exporter is currently failing.

### 5.2 Supporting feature metrics

| Metric | Feature |
|---|---|
| `aegismonitor_cpu_usage_pct` | CPU utilization percentage. |
| `aegismonitor_memory_usage_pct` | Memory utilization percentage. |
| `aegismonitor_disk_write_bytes_per_second` | Disk write throughput in bytes per second. |
| `aegismonitor_network_receive_bytes_per_second` | Network receive throughput in bytes per second. |
| `aegismonitor_load1` | System load average over one minute. |

These are the five features used by the P15 v2 model, in this exact order:

1. `cpu_usage_pct`
2. `memory_usage_pct`
3. `disk_write_bytes_per_second`
4. `network_receive_bytes_per_second`
5. `load1`

The score depends on the combined feature vector rather than any one metric in isolation.

### 5.3 Underlying Prometheus queries

The corresponding system-level PromQL expressions used to calculate the features are:

**CPU usage percentage**

```promql
100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))
```

**Memory usage percentage**

```promql
100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
```

**Disk write throughput**

```promql
sum(rate(node_disk_written_bytes_total[5m]))
```

**Network receive throughput**

```promql
sum(rate(node_network_receive_bytes_total{device!="lo"}[5m]))
```

**Load average**

```promql
node_load1
```

The CPU, disk, and network expressions use five-minute rate windows. These smooth brief workloads, so short spikes may not immediately produce large feature values. Network receive throughput excludes the loopback device `lo`.

These expressions document the underlying feature calculations; the dashboard's displayed feature panels use the exporter metrics where configured.

## 6. Integration and Provisioning

The dashboard is provisioned from:

`grafana/dashboards/anomaly-dashboard.json`

During integration, unresolved `${DS_PROMETHEUS}` datasource references were found in the dashboard JSON. There were 12 occurrences. These references were corrected, and Grafana was restarted to reload the dashboard.

Grafana logs subsequently showed:

- `starting to provision dashboards`
- `finished to provision dashboards`

The dashboard was then opened and checked. All 12 panels loaded and displayed data.

Messages about missing `/etc/grafana/provisioning/plugins` and `/etc/grafana/provisioning/alerting` directories were observed. They did not prevent the dashboard from provisioning or its panels from displaying data.

## 7. Validation and Results

### 7.1 Dashboard validation

The following were verified:

- The dashboard JSON was provisioned by Grafana.
- The dashboard was accessible using UID `aegis-anomaly-dashboard`.
- All 12 panels loaded and displayed data.
- The panels queried live Prometheus metrics.
- The normal-state status and supporting telemetry were visible.
- Evaluation-health and exporter-monitoring panels were available for diagnosing stale or failed evaluations.

### 7.2 Normal-state validation

During the validation period, the model continued to evaluate live system telemetry.

Observed behavior included:

- `aegismonitor_anomaly_candidate` remained `0`.
- No anomalous period was identified by the tested workload.
- The score changed in response to different system workloads.
- Evaluation-success metrics indicated successful evaluations during the reported checks.

The lowest score observed in the controlled tests was approximately:

`-0.6327325014216432`

The fixed threshold was:

`-0.670917882340376`

The observed minimum therefore remained approximately `0.038185` above the threshold. None of the recorded tests produced an anomaly candidate.

The tests included CPU and disk workloads, as well as earlier combined workloads. These were useful for confirming that the exporter and dashboard continued to operate, but they did not establish that the model can detect every type of anomaly.

### 7.3 Validation limitation

**The anomaly-state dashboard path has not been verified end to end.**

No tested workload caused the score to cross the fixed threshold. Consequently, the candidate flag remained `0`, and no real anomaly period was available to confirm the complete visualization path for a positive detection.

This limitation is explicitly recorded rather than treating the absence of an anomaly as proof that anomaly detection is fully validated.

No additional stress tests are required to consider the P16 dashboard implementation complete. The model and threshold remain unchanged.

## 8. Outcome

P16 is considered **complete**.

The dashboard integrates the existing P15 anomaly exporter with Grafana and provides a centralized view of anomaly scores, candidate status, evaluation health, affected hosts, anomalous periods, supporting telemetry, and exporter health.

The normal-state visualization and provisioning were verified. Positive anomaly-state visualization remains an outstanding validation limitation, not a reason to modify the model or threshold during P16.

## 9. Known Limitations and Future Considerations

- No tested workload crossed the existing threshold.
- The positive anomaly-state visualization path has not been confirmed end to end.
- The model's live-data baseline is exploratory and lacks ground-truth labels.
- The five-minute rate windows can smooth brief CPU, disk, and network events.
- A stale score or candidate flag can remain visible after an evaluation failure, so evaluation health and freshness must be checked.
- The exporter currently identifies the local host using `host="localhost"` and `env="local"`. Future multi-host support may require revisiting host identity and aggregation.
- Dashboard visualization alone does not implement durable event, alert, anomaly, or incident correlation.

## 10. Next Milestone — P17

The next roadmap milestone is **P17 — Implement the event/alert/anomaly data model**.

The P17 implementation should follow the established architecture decisions:

- Events, alerts, anomalies, and incidents are distinct concepts.
- Signals may have many-to-many relationships with incidents.
- Incident-to-signal associations use explicit per-type junctions.
- Association roles include primary, contributing, supporting, and evidence.
- Associations include a relevance score.
- Composite association identity uses `(incident_id, signal_id)`.
- UUIDs are used for entity identity.
- `LogSignature` applies only to log-origin events.
- PostgreSQL is the durable source of truth; Redis is ephemeral.

These are existing design decisions to preserve during P17. The schema is not to be finalized prematurely: migrations, enums, constraints, foreign keys, indexes, and the final schema remain deferred until P18, according to the roadmap.

## 11. Future-Conversation Handoff

When continuing this project in a new conversation, use this report as the P16 handoff reference.

**Known project state:**

- P1–P16 are complete.
- P15 uses the saved v2 Isolation Forest model and fixed threshold documented above.
- P16's 12-panel Grafana dashboard is provisioned and displaying data.
- The normal-state dashboard behavior has been validated.
- The positive anomaly-state path has not been verified because no tested score crossed the threshold.
- The model, hyperparameters, and threshold were not changed during P16.
- P17 is the next milestone.

**Before making implementation changes:**

1. Inspect the current Git status and repository history.
2. Read this report and the existing P15 documentation.
3. Inspect the actual dashboard JSON, exporter code, Prometheus configuration, and relevant Compose configuration.
4. Preserve existing architectural decisions and verify actual source files rather than assuming that this report necessarily reflects later code changes.
5. Continue one roadmap task at a time and validate each implementation step before proceeding.

**Repository context:**

- Repository: `~/Projects/AegisMonitor-AI`
- Dashboard: `grafana/dashboards/anomaly-dashboard.json`
- Exporter: `ml/anomaly_exporter/app.py`
- Model: `models/p15_live_isolation_forest_v2.joblib`
- Metadata: `models/p15_live_metadata_v2.json`
- P15 report: `docs/P15-isolation-forest.md`
- Monitoring commands must use Docker Compose's `dev` profile.

**Important Git note:** a deletion of `docs/current_state.txt` was intentional in the project workflow and must not be restored or committed merely to make the working tree clean.

This report documents the known P16 state. If the repository changes later, inspect the live source and Git history before treating the report as the definitive implementation state.