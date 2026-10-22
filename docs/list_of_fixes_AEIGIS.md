* **P1 — Event / Alert / Anomaly / Incident model**

  * Design the model with correlation in mind from the beginning.
  * Support **many-to-many relationships** between incidents and contributing signals.
  * One incident may contain:

    * multiple alerts
    * multiple anomalies
    * multiple event signatures
    * multiple raw evidence events
  * Avoid designing a flat `incident → single event` relationship that would require restructuring later.

* **P2 — PostgreSQL vs Redis responsibilities**

  * PostgreSQL = durable source of truth.
  * Redis = ephemeral operational state.
  * Define responsibilities before implementing the correlation layer.

* **P3 — Add Disk I/O to Host Overview**

  * Add disk read/write throughput.
  * Completes the planned telemetry foundation.

* **P4 — Define the AegisMonitor severity contract**

  * Formalize `PRIORITY`, `detected_level`, alert severity, anomaly severity, and incident severity.
  * Define the allowed severity vocabulary and semantics.

* **P5 — Pin Docker image versions**

  * Replace `latest` with tested versions.
  * Protect against unexpected Grafana/Loki/Prometheus/etc. updates.
  * Do this early because it is low-risk and becomes harder to retrofit later.
  * Record the tested versions in the project documentation.

* **P6 — Implement log signature normalization**

  * Add Fluent Bit Lua normalization.
  * Generate a `signature` field.
  * Preserve all original log information.
  * Keep the signature as a field initially.

* **P7 — Validate signature cardinality**

  * Test against real Fedora logs.
  * Measure unique signatures over time.
  * Tighten normalization if too many near-duplicate signatures appear.

* **P8 — Optionally promote signature to Loki label**

  * Only after confirming low cardinality.
  * Prefer tens of signatures rather than hundreds/thousands.
  * If cardinality is too high, keep it as a field permanently.

* **P9 — Update Grafana error visualization**

  * Raw Error Events panel.
  * Recurring Error Signatures panel.
  * Preserve the distinction between event count and recurring problems.

* **P10 — Build `scripts/load_gen.py`**

  * CPU.
  * Memory.
  * Disk I/O.
  * Network.
  * Error bursts.
  * Combined workloads.

* **P11 — Implement Prometheus alert rules**

  * CPU.
  * Memory.
  * Disk.
  * Host availability.
  * Disk I/O.
  * Signature/error-rate spikes.
  * Keep deterministic alerts separate from ML anomalies.

* **P12 — Add Alertmanager**

  * Grouping.
  * Deduplication.
  * Routing.
  * Inhibition.
  * Silencing.

* **P13 — Add Telegram notifications**

  * Prometheus → Alertmanager → Telegram.

* **P14 — Validate 30-day Prometheus retention**

  * Keep 30 days initially.
  * Determine whether the ML baseline needs more history.
  * Consider weekly and daily patterns.
  * Validate before changing retention.

* **P15 — Implement Isolation Forest**

  * CPU.
  * Memory.
  * Disk I/O.
  * Network I/O.
  * Load average.
  * Later expand with log/signature and temporal features if useful.

* **P16 — Build anomaly dashboard**

  * Anomaly scores.
  * Anomalous periods.
  * Affected hosts.
  * Supporting metrics/context.

* **P17 — Implement event/alert/anomaly correlation**

  * Correlate multiple signals into incidents.
  * Example:

    * CPU anomaly
    * network anomaly
    * `ath9k` signature burst
    * Prometheus alert
    * → one incident
  * P1's many-to-many model should support this without restructuring.

* **P18 — Integrate PostgreSQL**

  * Persist incidents.
  * Alerts.
  * Anomalies.
  * Signatures/events.
  * Relationships.
  * Status/history.
  * AI analysis.
  * Feedback.

* **P19 — Integrate Redis**

  * Deduplication.
  * Correlation windows.
  * Cooldowns.
  * Rate limiting.
  * Temporary state.
  * Caching.

* **P20 — Build FastAPI correlation/API layer**

  * Provide a structured interface between monitoring and AI/application components.

* **P21 — Define Prometheus/Loki → FastAPI interface**

  * Prometheus → metrics.
  * Loki → logs/signatures.
  * PostgreSQL → historical incidents.
  * Redis → ephemeral state.
  * FastAPI → structured incident context.

* **P22 — Add Ollama / LLM**

  * Only after structured incident context exists.
  * No uncontrolled raw-log dumps.

* **P23 — Implement AI incident analysis**

  * Summaries.
  * Evidence.
  * Contributing factors.
  * Affected components.
  * Investigation suggestions.
  * Uncertainty/confidence.

* **P24 — Add feedback / retraining loop**

  * AI analysis → human feedback → stored feedback → model improvement.

* **P25 — Make Grafana dashboards Git-controlled**

  * Keep UI editing enabled while dashboards are actively changing.
  * Once stable, make Git the source of truth.
  * Eventually disable UI updates.

* **P26 — Add healthchecks/readiness handling**

  * Prometheus.
  * Grafana.
  * Loki.
  * PostgreSQL.
  * Redis.
  * FastAPI.
  * Improve service readiness beyond basic startup ordering.

* **P27 — Final refinements**

  * Dynamic Grafana variables.
  * Better filesystem filtering.
  * Multi-host support.
  * Additional metrics.
  * Dashboard refinements.
  * Documentation/configuration cleanup.

* **Updated critical path:**

  * `Foundation`
  * → Event/Incident model
  * → PostgreSQL/Redis roles
  * → Disk I/O
  * → Severity contract
  * → **Pin Docker versions**
  * → Signature normalization
  * → Cardinality validation
  * → Optional Loki labels
  * → Error dashboard
  * → Load generator
  * → Prometheus alerts
  * → Alertmanager
  * → Telegram
  * → Retention validation
  * → Isolation Forest
  * → Anomaly dashboard
  * → Correlation
  * → PostgreSQL/Redis implementation
  * → FastAPI
  * → LLM
  * → Feedback/retraining

