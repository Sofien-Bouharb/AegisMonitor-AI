# P17 — Event, Alert, and Anomaly Correlation

## Objective

Correlate multiple monitoring signals into a single incident with explicit relationships, deterministic rules, and an explainable severity assessment.

## Implementation

The correlation engine is implemented in `ml/correlation/engine.py`. It uses Python's standard library and does not require external services.

Supported signal types:

- **Alert:** A deterministic monitoring alert, such as `HighCPUUsage`.
- **Anomaly:** A statistical anomaly candidate produced by the Isolation Forest model.
- **Log signature:** A recurring log pattern or signature burst.

The current implementation targets the local host, `localhost`.

## Correlation rules

1. Signals are grouped by occurrence time within a configurable correlation window, five minutes by default.
2. Signals from hosts other than the configured host are ignored.
3. An incident requires at least two distinct signal types.
4. At least one signal must be something other than an anomaly candidate. An anomaly candidate alone cannot create an incident.
5. Each incident preserves explicit relationships to its contributing signals.
6. Relationships record the signal ID, type, name, role, relevance score, and observation timestamps.
7. Incident severity is derived from a weighted evidence score and the number of distinct signal types.

Relationship roles are `primary`, `contributing`, `supporting`, and `evidence`. Relevance scores range from 0 to 1.

## Reproducible demonstration

The demonstration in `scripts/p17_demo.py` supplies three representative signals:

- CPU anomaly candidate.
- Prometheus `HighCPUUsage` alert.
- `ath9k` log-signature burst.

These signals fall within the same correlation window and produce one open incident on `localhost`.

Run the demonstration from the repository root:

```bash
python -m scripts.p17_demo
```

## Tests and validation

Run the automated tests:

```bash
python -m unittest discover -s tests -v
```

Seven tests currently cover:

- Correlation of multiple signal types into one incident.
- Rejection of an anomaly candidate on its own.
- Correlation of an anomaly candidate with an alert.
- Separation of signals outside the time window.
- Ignoring signals from other hosts.
- Preservation of signal IDs and timestamps.
- Explicit relationship roles.

All seven tests passed during P17 validation.

## Scope and limitations

P17 implements the correlation core and a reproducible demonstration. It does not yet persist incidents or maintain correlation state across separate executions.

- PostgreSQL persistence is deferred to P18.
- Redis-based deduplication and temporary correlation state are deferred to P19.
- FastAPI integration is deferred to P20.
- Live signal ingestion and integration are deferred to later milestones.

The demonstration uses representative inputs; it does not establish that live production signals are already being correlated.

## Status

**P17 core implementation and acceptance demonstration completed.** Final repository review and checkpoint commit remain to be performed.
