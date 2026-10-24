# AegisMonitor AI

## Consolidated Technical Report — P1 to P27

**Project status:** Complete — Portfolio MVP  
**Project type:** Personal portfolio project  
**Reporting date:** 24 October 2026  
**Repository:** `~/Projects/AegisMonitor-AI`  
**Primary branch:** `main`  
**Runtime environment:** Fedora Linux, Docker Compose, local/self-hosted infrastructure  
**AI runtime:** Ollama with `llama3.1:8b`

---

# 1. Executive Summary

AegisMonitor AI is a local, self-hosted monitoring and anomaly-analysis platform that combines infrastructure telemetry, log collection, deterministic alerting, machine-learning anomaly detection, multi-signal correlation, persistent incident-related data, and local large language model analysis.

The project was developed through 27 milestones, progressing from monitoring infrastructure and signal-model design to anomaly detection, correlation, API integration, AI-assisted analysis, human feedback persistence, service health checks, and dashboard refinements.

The completed portfolio MVP integrates the following capabilities:

- Infrastructure monitoring through Prometheus and Node Exporter.
- Log collection and exploration through Fluent Bit and Loki.
- Grafana dashboards for host metrics, logs, and anomaly telemetry.
- Deterministic Prometheus alert rules and Alertmanager routing.
- Telegram notifications for firing and resolved alerts.
- An Isolation Forest baseline for identifying unusual telemetry patterns.
- A correlation engine that combines different signal types into incident candidates.
- Redis-backed alert deduplication and temporary, per-host correlation windows.
- PostgreSQL persistence for supported incidents, relationships, AI analyses, and human feedback.
- FastAPI endpoints for signal correlation, structured context retrieval, local text generation, AI-assisted analysis, and feedback submission.
- Docker Compose health checks and service startup dependencies.
- Git-controlled Grafana dashboards and initial multi-host target-discovery configuration.

The project remains local and self-hosted for its core functionality. Its AI generation and analysis workflow uses Ollama rather than requiring a cloud AI provider.

**Completion does not mean every proposed capability is production-ready.** The MVP has documented boundaries, including limited database relationship persistence, unverified remote-host scraping, an exploratory rather than ground-truth-validated anomaly detector, and the absence of automated feedback-driven retraining.

The appropriate final status is **COMPLETE — PORTFOLIO MVP**, with future enhancements managed as separately scoped work.

# 2. Project Objectives

The project aims to demonstrate how traditional infrastructure monitoring can be extended with machine learning, event correlation, durable data storage, and locally hosted AI analysis.

The main objectives were to:

1. Establish a reproducible, containerized monitoring and logging environment.
2. Preserve clear distinctions between events, alerts, anomalies, and incidents.
3. Combine deterministic monitoring rules with exploratory anomaly detection.
4. Correlate related signals while retaining traceable relationships to their evidence.
5. Separate durable historical records from temporary operational state.
6. Expose monitoring and correlation functionality through an HTTP API.
7. Collect structured operational context for AI-assisted analysis.
8. Persist generated analyses and human feedback.
9. Improve service health visibility, dashboard usability, and configuration maintainability.
10. Keep the core environment locally deployable and suitable for a personal engineering portfolio.

# 3. Architecture Overview

## 3.1 Monitoring and telemetry

The monitoring layer collects host metrics and exposes them through Prometheus.

| Component     | Responsibility                                                         |
| ------------- | ---------------------------------------------------------------------- |
| Node Exporter | Exposes host and system metrics                                        |
| Prometheus    | Scrapes metrics, evaluates alert rules, and retains time-series data   |
| Grafana       | Visualizes infrastructure metrics, logs, and anomaly-related telemetry |
| Fluent Bit    | Collects and processes logs                                            |
| Loki          | Stores and queries log data                                            |
| Alertmanager  | Groups, routes, and manages alert notifications                        |
| Telegram      | Receives firing and resolved alert notifications                       |

The reported Prometheus configuration uses a 15-second scrape interval and 30-day retention. The local Node Exporter target is configured with the labels `host=localhost` and `env=local`.

Docker image versions are pinned in the reported stack rather than relying on floating `latest` tags. The reported versions include Prometheus 3.14.0, Grafana 13.2.2, Loki 3.7.8, Fluent Bit 5.1.2, Alertmanager 0.29.0, PostgreSQL 16-alpine, Redis 7-alpine, and Node Exporter 1.12.1.

These are the documented versions for the project environment, not a claim that every version remains the latest available.

## 3.2 Anomaly detection

The anomaly-detection component uses a saved Isolation Forest model to score current host telemetry.

The anomaly exporter evaluates the current feature vector and exposes metrics to Prometheus. Grafana then visualizes the score, candidate status, evaluation health, and related host measurements.

The model identifies statistical candidates for investigation. Its output is not, by itself, a confirmed incident.

## 3.3 Correlation and incident context

The correlation engine combines different types of signals within a configurable time window. Redis supplies temporary correlation state, while PostgreSQL stores supported durable records.

The FastAPI correlation service exposes this functionality over HTTP. A separate context-collection layer retrieves relevant Prometheus metrics, recent Loki logs, and previously persisted PostgreSQL incidents.

## 3.4 Local AI analysis and feedback

The AI workflow uses a local Ollama model to generate text and analyze collected monitoring context.

The analysis endpoint returns both generated analysis and its structured evidence context. Successful analyses and submitted human feedback are stored in PostgreSQL.

The AI output is decision support. It does not replace telemetry, establish a root cause automatically, or turn an anomaly candidate into a confirmed incident.

## 3.5 Architectural flow

The intended operational flow is:

1. Collect host telemetry and logs.
2. Evaluate deterministic alert rules and score telemetry with the anomaly model.
3. Expose alerts, anomaly candidates, and log evidence.
4. Correlate qualifying signals using the correlation engine and temporary Redis state.
5. Retrieve monitoring context through the FastAPI context interface.
6. Generate a local AI-assisted interpretation of that context.
7. Persist the generated analysis and its evidence.
8. Accept and persist human feedback.

**Important implementation boundary:** correlation results returned by the API are not automatically persisted as PostgreSQL incidents by the correlation endpoint. Consequently, the AI context collector reads previously persisted incidents rather than automatically receiving every newly generated correlation result.

# 4. Core Data Model and Design Principles

## 4.1 Distinct operational concepts

AegisMonitor AI deliberately avoids representing every operational observation as one generic signal record.

| Concept      | Meaning                                                               |
| ------------ | --------------------------------------------------------------------- |
| Event        | An observed occurrence that is not necessarily abnormal or actionable |
| Alert        | A deterministic rule firing, such as sustained high CPU usage         |
| Anomaly      | A statistically unusual observation produced by the anomaly detector  |
| LogSignature | A recurring log pattern or signature                                  |
| Incident     | A higher-level situation formed by correlating relevant evidence      |

An alert is not automatically an incident. An anomaly is not automatically an incident. A log signature is a log-specific concept rather than a generic pattern for all signal types.

## 4.2 Explicit relationships

The design uses explicit many-to-many relationships between incidents and supported signal types rather than a generic `signal_type`/`signal_id` relationship without proper foreign keys.

Relationship metadata includes:

- Relationship role: `primary`, `contributing`, `supporting`, or `evidence`.
- Relevance score between 0 and 1.
- First-seen and last-seen timestamps.
- References to the corresponding signal.

This preserves the ability to explain which evidence contributed to a correlation result.

The reported PostgreSQL implementation supports Alert and Anomaly relationships in the persistence slice. LogSignature relationship persistence remains unsupported and raises `NotImplementedError`. Full persistence for every originally planned Event and LogSignature workflow should not be assumed.

## 4.3 Severity semantics

The operational severity vocabulary is `info`, `warning`, `error`, and `critical`.

The project preserves distinctions between:

- `PRIORITY`: an original source-system priority, such as a systemd priority.
- `detected_level`: a log-level classification.
- Operational severity: the importance assigned to an alert, anomaly, or incident.

Incident severity is intended to consider the correlated evidence, relationship relevance, and context rather than blindly inheriting the severity of the first signal or the highest-severity low-relevance signal.

## 4.4 Durable and ephemeral state

PostgreSQL is the durable source of truth for supported historical records. Redis is used for temporary operational state, including alert deduplication and per-host correlation windows.

Historical incident, analysis, and feedback records are not intended to depend on Redis surviving a restart.

# 5. Milestone Summary

The project completed milestones P1–P27. The following summarizes their documented scope and final status.

## 5.1 Foundation and monitoring — P1 to P14

**P1 — Operational data model**

Defined the separate Event, Alert, Anomaly, LogSignature, and Incident concepts, with explicit incident relationships and role/relevance metadata.

**P2 — Persistence responsibilities**

Established PostgreSQL as the durable store and Redis as the ephemeral operational-state store.

**P3 — Disk I/O visibility**

The supplied project decision report identifies P3 as complete. The broader roadmap specifies adding disk read/write throughput to the Host Overview. A separate detailed P3 implementation and validation report was not included in the material consolidated here.

**P4 — Severity contract**

Defined the shared operational severity vocabulary and distinguished it from source-system priority and log-level classification.

**P5 — Pinned image versions**

The project stack uses documented, version-pinned container images rather than floating `latest` tags.

**P6–P8 — Log signatures and cardinality**

The roadmap covers log-signature normalization, validation against Fedora logs, and conditional promotion to Loki labels only if cardinality remains suitably low. Detailed milestone-specific test evidence for these items was not included in the supplied reports.

**P9 — Log dashboards**

The roadmap calls for distinguishing raw error events from recurring error signatures. Later dashboard refinements add host and service filtering to the Log Explorer.

**P10 — Load generation**

The project includes `scripts/load_gen.py` for controlled resource-load scenarios. This was used in reported alert validation, including CPU tests.

**P11 — Prometheus alert rules**

Implemented six infrastructure alert rules:

- `HighCPUUsage`: CPU above 85% for 2 minutes, warning.
- `HighMemoryUsage`: memory above 90% for 2 minutes, warning.
- `LowDiskSpace`: root filesystem available space below 10% for 2 minutes, warning.
- `HostDown`: Node Exporter target unavailable for 1 minute, critical.
- `HighDiskReadRate`: aggregate disk read rate above 100,000,000 bytes/s for 2 minutes, warning.
- `HighDiskWriteRate`: aggregate disk write rate above 100,000,000 bytes/s for 2 minutes, warning.

Disk rules exclude loop and RAM devices. Rules were validated with `promtool`, and controlled tests confirmed alert firing. Temporary test thresholds were used for disk I/O and disk-space scenarios, then removed. Production thresholds were restored.

**P12 — Alertmanager**

Integrated Alertmanager 0.29.0 with Prometheus, including grouping, default and critical routes, persistent silence storage, and runtime readiness validation.

A live warning alert was verified through Prometheus and Alertmanager. The report did not establish a complete end-to-end test of every critical route, multi-alert grouping scenario, inhibition scenario, or silence scenario.

**P13 — Telegram notifications**

Integrated Telegram notifications through Alertmanager. A controlled CPU alert produced a firing notification, and recovery produced a resolved notification. Secret files remain local and were not added to Git.

**P14 — Prometheus retention**

The documented Prometheus configuration uses 30-day retention. The complete milestone-specific evidence for a full retention-period validation was not included in the supplied reports; configured retention should not be confused with proof of a 30-day historical observation.

## 5.2 Anomaly detection and correlation — P15 to P19

**P15 — Isolation Forest anomaly detection**

Implemented a saved Isolation Forest v2 baseline, training and evaluation scripts, model metadata, and an application-level anomaly threshold.

**P16 — Anomaly dashboard**

Provisioned a 12-panel Grafana anomaly dashboard with live score, candidate status, evaluation health, anomalous-period, exporter-health, and feature-telemetry panels.

**P17 — Correlation engine**

Implemented a standard-library correlation engine with a five-minute default window. It groups signals by host and time, requires at least two distinct signal types and at least one non-anomaly signal, and retains explicit signal relationships.

Seven correlation tests passed. A demo produced an incident from an anomaly candidate, a Prometheus alert, and a log-signature burst. This demonstrates the engine's behavior but is not evidence of a complete live ingestion-to-persistence workflow.

**P18 — PostgreSQL integration**

Implemented a limited database integration slice for incident persistence and supported Alert/Anomaly relationships. Fifteen database tests were reported as passing, with live checks for connectivity, foreign-key enforcement, rollback, incident persistence, and alert linkage.

Full Event/LogSignature persistence, automatic persistence of every anomaly candidate, and the complete incident lifecycle were not established by the supplied evidence.

**P19 — Redis operational state**

Intentionally closed with reduced scope after implementing:

- Redis-backed alert delivery deduplication.
- Temporary per-host correlation-window storage.
- Signal serialization, expiration, and pruning of old window entries.

The alert deduplication key incorporates alert fingerprint, status, start time, and end time, with a default TTL of 300 seconds. Correlation-window storage uses Redis sorted sets and hashes.

Cooldowns, rate limiting, and general-purpose caching were deferred. The reported correlation-window operations are not fully atomic, and the window configuration helper has a documented default-parameter caveat that callers must account for.

## 5.3 API and AI integration — P20 to P24

**P20 — FastAPI correlation API**

Added `POST /api/v1/correlate` and a process-level `GET /health` endpoint. The API validates requests, stores signals in Redis-backed host-specific windows, invokes the correlation engine, serializes incident relationships, and returns HTTP 503 when Redis is unavailable.

The full Python suite passed 58 tests at the reported checkpoint; 11 focused API tests passed. A live two-request Redis-backed test confirmed cross-request correlation. The endpoint does not automatically persist returned incidents to PostgreSQL.

**P21 — Structured monitoring context**

Introduced the context-retrieval layer for Prometheus anomaly metrics, recent Loki logs, and persisted PostgreSQL incidents. The intended endpoint is `GET /api/v1/context/metrics`.

The implementation uses bounded retrieval and represents unavailable metric values explicitly rather than converting them to zero. Loki and database failures can degrade their respective context sections without necessarily preventing the whole response.

The supplied P21 report was incomplete, ending during its response-shape section. Its exact full-suite result and complete live-validation evidence therefore cannot be independently summarized from that report alone.

**P22 — Local Ollama integration**

Added `POST /api/v1/ai/generate`, backed by a local Ollama service using `llama3.1:8b`. The endpoint validates prompts, rejects unexpected fields, and maps generation failures to HTTP 503.

The full suite passed 99 tests at the reported checkpoint. A live generation request returned HTTP 200. This milestone established text generation, not context-aware incident analysis.

**P23 — Evidence-grounded AI analysis**

Added `POST /api/v1/ai/analyze`, reusing the existing context collector and Ollama client.

The endpoint returns generated analysis alongside the structured evidence context. Prompt instructions require the model to distinguish observations from hypotheses, disclose unavailable evidence, treat logs and incident text as untrusted evidence, and avoid treating an anomaly candidate alone as a confirmed incident.

Validation included 102 passing tests, successful Compose configuration checks, a clean diff check, and a live request returning HTTP 200.

The live output illustrated why temporal proximity does not prove causation: healthcheck errors and Docker networking events were observed, but the evidence did not establish a root cause.

**P24 — Human feedback persistence**

Added the `ai_analyses` and `ai_feedback` PostgreSQL tables through `migrations/002_ai_feedback.sql`.

The analysis endpoint now persists generated text and its context. The feedback endpoint stores a verdict linked to the analysis, with supported verdicts `helpful`, `not_helpful`, `correct`, and `incorrect`.

Validation included 114 passing tests, migration verification, successful live analysis and feedback requests, and a direct database join confirming that the two records were persisted and correctly linked.

Automated retraining, feedback analytics, a review interface, and feedback-driven model updates remain deferred.

## 5.4 Final refinements — P25 to P27

**P25 — Git-controlled Grafana dashboards**

The project adopted Git-controlled dashboard provisioning. Dashboard definitions are stored in the repository to improve reproducibility and make dashboard changes reviewable. The supplied project context identifies P25 as complete.

**P26 — Health checks and readiness**

Added Docker health checks for PostgreSQL, Redis, FastAPI, Prometheus, and Grafana. The `alert-receiver` and `correlation-api` services wait for PostgreSQL and Redis to become healthy before starting.

Compose configuration validation passed for the `dev`, `ai`, and `full` profiles. Loki's `/ready` endpoint was verified separately because the tested image did not contain the required in-container probe utilities.

The API health check is a liveness check, not a comprehensive dependency-readiness test. Docker's unhealthy status does not by itself guarantee container restart.

**P27 — Final monitoring dashboards and multi-host configuration**

Completed the final reported dashboard refinements:

- Added Host and Service variables to the Log Explorer.
- Excluded `tmpfs` and `vfat` filesystems from the relevant filesystem panel.
- Added a CPU Pressure (%) panel and visually verified it.
- Added `prometheus/targets/node-exporters.yml` for file-based Node Exporter target discovery.
- Documented the setup in `docs/multi-host-node-exporter.md`.

Compose, dashboard JSON, Prometheus configuration, target YAML, and Git patch validation passed. The local Node Exporter target was `UP`, and Grafana was healthy.

Remote-host scraping was explicitly not tested end to end.

# 6. Isolation Forest Implementation and Evaluation

The anomaly detector is an exploratory unsupervised baseline, not a fully ground-truth-validated production detector.

## 6.1 Model configuration

The reported v2 model uses these features in the exact order shown:

1. `cpu_usage_pct`
2. `memory_usage_pct`
3. `disk_write_bytes_per_second`
4. `network_receive_bytes_per_second`
5. `load1`

The documented hyperparameters are:

| Parameter       | Value  |
| --------------- | ------ |
| `n_estimators`  | 200    |
| `max_samples`   | `auto` |
| `contamination` | `auto` |
| `random_state`  | 42     |
| `n_jobs`        | -1     |
| `max_features`  | 1.0    |
| `bootstrap`     | False  |

The saved model is `models/p15_live_isolation_forest_v2.joblib`, with associated metadata at `models/p15_live_metadata_v2.json`.

The application threshold is:

`-0.670917882340376`

A sample is an anomaly candidate only when its `score_samples()` score is **strictly less than** this threshold. The threshold is separate from scikit-learn's `contamination=auto` parameter.

## 6.2 Reported evaluation

The model was fit on a chronological telemetry partition of 938 samples. A later calibration partition contained 235 samples, from which the first-percentile threshold was selected. Three calibration samples, approximately 1.28%, were flagged.

A later, chronologically unseen evaluation contained 247 samples. Seven samples, approximately 2.83%, were flagged. They occurred in a continuous period on 17 October 2026, with disk-write rates around 19.0–19.7 MB/s and CPU usage around 5–9%.

The available journal evidence did not explain those observations. Their cause could not be determined from the recorded evidence.

An exploratory SMD benchmark reported approximately 0.67 F1, 0.946 ROC-AUC, and 0.6405 average precision. Feature selection was influenced by test labels, so these figures must not be presented as an unbiased final benchmark or compared directly with the unlabeled live evaluation.

## 6.3 Evaluation limitations

- Live telemetry has no verified ground-truth labels.
- The training period was not proven to contain only normal behavior.
- The live evaluation covers a limited time window and a single host.
- A candidate indicates unusualness under the model, not malicious activity or a confirmed incident.
- The Grafana dashboard's positive anomaly state was not validated end to end during the reported controlled tests. The lowest controlled-test score was approximately -0.632733, above the application threshold.
- Five-minute rate windows can smooth short-lived spikes.
- A failed evaluation can leave score and candidate metrics stale; evaluation-health metrics must be considered alongside them.

The model, feature order, and saved threshold were preserved during the later API and AI milestones.

# 7. AI Analysis, Evidence Handling, and Persistence

## 7.1 Generation and analysis endpoints

The local AI workflow exposes two distinct capabilities:

- `POST /api/v1/ai/generate`: generates text from a supplied prompt.
- `POST /api/v1/ai/analyze`: collects existing monitoring context and asks the local model to analyze it.

This distinction matters. P22 proves that the local model can be called. P23 connects generation to collected monitoring evidence.

The analysis endpoint treats Prometheus context and Ollama generation as required steps. Their failures produce HTTP 503. Loki and PostgreSQL context failures can be represented as unavailable sections through the existing collector's partial-availability behavior.

## 7.2 Evidence-grounding safeguards

The prompt asks the model to:

- Use only supplied evidence.
- Separate direct observations from hypotheses.
- Disclose unavailable evidence.
- Avoid inventing telemetry or log entries.
- Treat log messages and incident text as untrusted evidence rather than instructions.
- Avoid interpreting an anomaly candidate as a confirmed incident.

These are useful prompt-level safeguards, not hard security boundaries. The model may still generate inaccurate or unsupported claims.

## 7.3 Analysis and feedback storage

P24 makes successful analyses and their context durable in PostgreSQL. Human feedback is linked to the specific analysis it evaluates.

This supports future review and evaluation, but the system does not yet establish a feedback-driven training pipeline. Feedback may be incomplete, subjective, or incorrect, and must not automatically be treated as ground truth.

# 8. Validation Summary

The reports provide milestone-specific evidence rather than one single test run covering every feature at the final checkpoint.

| Milestone or area             | Reported validation                                                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| P11 alert rules               | Six rules loaded by `promtool`; controlled alert transitions verified                                                     |
| P12 Alertmanager              | Configuration and runtime integration verified; live warning routed                                                       |
| P13 Telegram                  | Firing and resolved notifications received                                                                                |
| P15 anomaly baseline          | Chronological calibration and later unseen-period evaluation performed                                                    |
| P16 anomaly dashboard         | Twelve panels provisioned and live data visible; positive state not verified                                              |
| P17 correlation engine        | Seven tests passed; demonstration created a multi-signal incident                                                         |
| P18 database integration      | Fifteen database tests passed; live persistence and foreign-key behavior checked                                          |
| P19 Redis correlation windows | Eleven focused tests and real Redis integration reported; 47-test suite passed before the final correlation-window commit |
| P20 correlation API           | 58 full-suite tests, 11 focused API tests, and live cross-request Redis integration passed                                |
| P21 structured context        | Client tests reported: nine Prometheus tests and eight Loki tests; full report was incomplete                             |
| P22 Ollama generation         | 99 full-suite tests passed; live generation returned HTTP 200                                                             |
| P23 AI analysis               | 102 full-suite tests passed; live local-stack request returned HTTP 200                                                   |
| P24 feedback persistence      | 114 full-suite tests passed; live records and relationship verified directly in PostgreSQL                                |
| P26 health checks             | Compose validation passed for `dev`, `ai`, and `full`; service probes checked                                             |
| P27 dashboard refinements     | Dashboard, Prometheus, target YAML, Compose, and Git patch checks passed                                                  |

These test counts belong to different historical checkpoints. They are not additive and should not be described as a single final test count. The evidence demonstrates incremental validation; it does not establish that every earlier integration test was rerun after every later change.

# 9. Security and Operational Considerations

## 9.1 Secrets

Telegram credentials are kept in local secret files under:

`~/.config/aegismonitor/secrets/`

The reports state that tokens were not added to Git. Alertmanager requires appropriate file permissions because it runs as an unprivileged container user. The reported setup uses restricted permissions rather than making the secret broadly readable.

## 9.2 Network boundaries

The Ollama service is reached from the container through the host's Docker bridge gateway. The reported address `172.18.0.1` is specific to the tested network and may change if the Docker network configuration changes.

The listener is not exposed on the host's Wi-Fi interface in the documented setup, but network reachability is not authentication. Containers able to reach the listener can potentially call it.

## 9.3 API access control

Authentication and authorization are not implemented in the reported API milestones. Rate limiting, streaming, asynchronous analysis jobs, and a dedicated review interface are also outside the current MVP.

Before exposing the API beyond its trusted local environment, access control, response size, context sensitivity, and network boundaries should be reviewed.

## 9.4 Health and recovery

Health checks improve startup coordination and failure visibility but do not replace application-level timeouts, retries, or runtime recovery. In particular, the API's `/health` endpoint does not verify every downstream dependency.

# 10. Known Limitations

The following limitations should be stated explicitly when presenting the project.

1. **Anomaly detection is exploratory.** Live ground truth is unavailable, and model performance has not been conclusively established against labeled production-like telemetry.
2. **Positive anomaly dashboard behavior remains unverified.** Normal-state telemetry and evaluation-health monitoring were validated, but a positive candidate state was not observed in the controlled dashboard tests.
3. **Correlation results are not automatically persisted.** The correlation API returns results and uses Redis for temporary state, but it does not automatically save every generated incident to PostgreSQL.
4. **Persistence covers a limited relationship slice.** Alert and Anomaly relationships are supported in the reported PostgreSQL integration; LogSignature relationship persistence remains unsupported.
5. **Remote-host scraping is unverified.** File-based target discovery is configured, but end-to-end remote Node Exporter collection has not been tested.
6. **AI output is not authoritative.** Generated hypotheses require corroboration, and prompt instructions cannot guarantee factual accuracy.
7. **Feedback does not trigger retraining.** Feedback persistence is implemented, but analytics, review workflows, and automated retraining remain deferred.
8. **Readiness is not comprehensive.** Several services have Docker health checks, but Loki is checked separately and the API health endpoint is a liveness check.
9. **Some maintenance work remains.** The reported Starlette/httpx test-client deprecation warning was not addressed during the AI milestones.
10. **P21 evidence is incomplete in the supplied report.** Its implementation is described, but its full final validation and closure details were not included in the provided text.

These are documented boundaries of the current portfolio MVP rather than evidence that the entire project is incomplete.

# 11. Repository and Delivery Status

The P27 implementation report identifies the final dashboard and multi-host configuration commit:

`1fb4b13` — `p27: finalize monitoring dashboards and multi-host configuration`

A subsequent repository checkpoint supplied for the P27 report identifies:

`f6c3300` — `p27: report`

At that later checkpoint, the user-confirmed Git status was:

```text
## main...origin/main
f6c3300 (HEAD -> main, origin/main, origin/HEAD) p27: report
```

This indicates that the reported local `main` branch was synchronized with `origin/main` and the working tree was clean at that checkpoint.

The repository should not be assumed to have a different current state without a fresh check. Earlier milestone reports describe uncommitted changes at their historical checkpoints, but those reports predate the final P27 repository state.

# 12. Recommended Future Work

No additional implementation milestone is required to declare the current roadmap complete. Future work should be separately scoped according to practical value.

## Priority 1 — Portfolio presentation

- Review and finalize the README.
- Document architecture and major data flows.
- Add Grafana dashboard screenshots.
- Document installation, startup, validation, and troubleshooting commands.
- Explain which features are implemented, which were validated, and which remain untested.
- Present anomaly detection as an exploratory baseline rather than claiming proven production accuracy.

## Priority 2 — Validate remote-host monitoring

- Configure Node Exporter on a second host.
- Verify network connectivity and firewall rules.
- Add the remote target to `prometheus/targets/node-exporters.yml`.
- Confirm that the remote target becomes `UP`.
- Verify that Grafana host variables and dashboards show the remote host correctly.
- Document the required network configuration.

## Priority 3 — Review incident persistence

Before connecting correlation results to durable incident persistence:

- Define stable incident identity and deduplication semantics.
- Decide when a correlation result should create or update a persisted incident.
- Prevent repeated requests from creating duplicate incidents.
- Preserve the distinctions between events, alerts, anomalies, and incidents.
- Add repository and API tests for creation, updates, relationships, and failure handling.

## Priority 4 — Evaluate AI analysis quality

- Build a small set of known monitoring scenarios with expected evidence and conclusions.
- Evaluate whether generated claims are supported by supplied context.
- Measure unsupported causal claims and missing-evidence handling.
- Add feedback analytics only when there is a clear evaluation objective.
- Treat retraining as a separate project requiring representative data and independent validation.

## Priority 5 — Review API security before broader exposure

- Decide whether authentication and authorization are required for the intended deployment.
- Restrict access to collected logs, incident details, and analysis context.
- Review Ollama network reachability.
- Consider rate limits and request-duration controls if the API is exposed to more callers.

# 13. Final Assessment

AegisMonitor AI demonstrates a coherent progression from traditional infrastructure monitoring to a local, AI-assisted monitoring workflow.

Its strongest engineering aspects are the explicit separation of operational data concepts, the separation of durable and ephemeral state, controlled alert validation, the integration of a saved anomaly model, traceable correlation relationships, a reusable structured-context layer, local LLM inference, and persistent analysis feedback.

The reports also preserve important limitations rather than treating every planned capability as production-ready. The anomaly model remains exploratory, remote-host monitoring is configured but not fully tested, correlation incidents are not automatically persisted by the API, and AI conclusions require human judgment and corroborating evidence.

The project has completed milestones P1–P27 and reached its stated portfolio-MVP objective.

**Final status: COMPLETE — PORTFOLIO MVP.**

Further improvements should be tracked as independent, explicitly scoped tasks. The current milestone roadmap does not need to be extended merely to claim additional functionality.
