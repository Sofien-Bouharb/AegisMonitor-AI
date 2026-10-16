# AegisMonitor AI — 7-Day Completion Roadmap

Target: complete the project before exams · Duration: 7 days · Approach: MVP-first, one milestone at a time

## Roadmap overview

Day 1 — P15: Isolation Forest

Finish the experiment, validate data partitioning and threshold calibration, evaluate unseen data, and document results.

Day 2 — P16: Anomaly dashboard

Visualize scores, anomalous periods, affected hosts and supporting metrics.

Day 3 — P17: Event and incident correlation

Correlate anomalies, Prometheus alerts and log signatures into incidents with traceable relationships.

Day 4 — P18–P19: PostgreSQL and Redis

Persist incidents and relationships; implement deduplication, correlation windows and cooldowns.

Day 5 — P20–P21: FastAPI and data integration

Connect Prometheus, Loki, PostgreSQL and Redis to a structured incident API.

Day 6 — P22–P24: AI analysis and feedback

Integrate Ollama, generate evidence-based incident analysis, and persist human feedback.

Day 7 — P25–P27: Stabilization and delivery

Provision dashboards through Git, validate readiness, run regression tests and finish documentation.

## Detailed milestones and acceptance criteria

| Day | Milestones | Completion criteria                                                                                                                 |
| --- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1   | P15        | Reproducible Isolation Forest experiment, valid evaluation on unseen data, documented results.                                      |
| 2   | P16        | Grafana displays anomaly scores, flagged periods and supporting metrics.                                                            |
| 3   | P17        | A reproducible scenario combines multiple signals into one incident with explicit relationships.                                    |
| 4   | P18–P19    | Incidents survive restarts; Redis handles temporary correlation state and deduplication.                                            |
| 5   | P20–P21    | FastAPI returns structured incident context sourced from the monitoring and storage services.                                       |
| 6   | P22–P24    | Ollama analyzes structured context, and human feedback is stored against the corresponding analysis.                                |
| 7   | P25–P27    | Stable dashboards are Git-controlled, essential healthchecks work, the stack passes regression tests, and documentation is updated. |

## Critical path

P15 — Isolation Forest

P16 — Anomaly dashboard

P17 — Correlation

P18 — PostgreSQL

P19 — Redis

P20 — FastAPI

P21 — Data interfaces

P22 — Ollama

P23 — AI analysis

P24 — Feedback

Parallel / finalization track

P25 — Git-controlled dashboards

P26 — Healthchecks and readiness

P27 — Refinements and documentation

P25 can begin earlier if the dashboards are stable. P26 should be implemented alongside integration where convenient, then validated on Day 7.

## Scope rules

- Complete: P15–P18, P20–P23 and the essential parts of P25–P27.
- Keep P19 minimal: prioritize deduplication, correlation windows and cooldowns.
- P24: implement feedback persistence; defer automated retraining if time is insufficient.
- P27: defer advanced multi-host support and nonessential refinements until the end-to-end workflow works.

Important: P15 is not complete yet. Day 1 begins by inspecting the current implementation and experiment artifacts, not by assuming the detector is ready.

The final objective is one working demonstration: detect an anomaly → correlate evidence → persist an incident → retrieve structured context → generate AI analysis → store human feedback, while keeping the existing monitoring infrastructure operational.