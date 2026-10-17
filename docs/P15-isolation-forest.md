# P15 — Isolation Forest Anomaly Detection

## 1. Objective

Implement an Isolation Forest baseline that identifies potentially anomalous
host telemetry. The detector complements deterministic Prometheus alert rules;
an anomaly candidate is not automatically a confirmed incident.

## 2. Input telemetry

The live collector is `ml/p15_collect_telemetry.py`. It queries Prometheus
and appends timestamped observations to `data/telemetry/live_metrics.csv`.

The model uses these five features, in this exact order:

1. `cpu_usage_pct`
2. `memory_usage_pct`
3. `disk_write_bytes_per_second`
4. `network_receive_bytes_per_second`
5. `load1`

The live telemetry CSV is local data and is not committed to Git.

## 3. Model configuration

The selected live baseline is v2:

- Algorithm: scikit-learn `IsolationForest`
- Estimators: 200
- `max_samples`: `auto`
- `contamination`: `auto`
- Random seed: 42
- `max_features`: 1.0
- `bootstrap`: false
- `n_jobs`: -1

Artifacts:

- Training: `ml/p15_train_live_v2.py`
- Model: `models/p15_live_isolation_forest_v2.joblib`
- Metadata: `models/p15_live_metadata_v2.json`
- Evaluation: `ml/p15_evaluate_live.py`

The v1 artifacts are retained separately under `models/archive/`.

## 4. Training and calibration partition

The v2 training script uses a chronological 80/20 split of the selected newer
live telemetry period. The earlier four initial test samples and the original
v1 baseline collection are excluded.

| Partition   | Samples | UTC period                      |
| ----------- | ------: | ------------------------------- |
| Fit         |     938 | 2026-10-15 15:26:54 to 19:46:56 |
| Calibration |     235 | 2026-10-15 19:47:11 to 21:17:44 |

The timestamps above are rounded for readability. Exact timestamps are stored
in `models/p15_live_metadata_v2.json`.

The model is fitted only on the fitting partition. The calibration partition
is used to select the application threshold.

## 5. Threshold calibration

The application threshold is the 1st percentile of `score_samples()` on the
calibration partition:

`-0.670917882340376`

A sample is flagged when its score is strictly lower than this threshold.
Lower `score_samples()` values indicate more anomalous observations.

The model's `contamination="auto"` setting and the separately calibrated
application threshold serve different purposes. The application uses the
saved calibrated threshold.

Calibration flagged 3 of 235 observations (approximately 1.28%). This is a
calibration result, not a guarantee of a 1% future anomaly rate or false
positive rate.

## 6. Unseen telemetry evaluation

The evaluator loads the saved v2 model and metadata without retraining. It
evaluates CSV samples strictly later than the recorded calibration end time.

Evaluation period: 2026-10-17 09:15:00 to 10:16:31 UTC.

| Metric           |          Result |
| ---------------- | --------------: |
| Unseen samples   |             247 |
| Fixed threshold  | -0.670917882340 |
| Flagged samples  |               7 |
| Flagged fraction |           2.83% |
| Minimum score    |       -0.727162 |
| Mean score       |       -0.461910 |
| Maximum score    |       -0.360687 |

All seven flagged observations occurred in one continuous period from
09:43:15 to 09:44:45 UTC on 2026-10-17. Disk writes were approximately
19.0–19.7 MB/s during this period. CPU usage was approximately 5–9%.

A check of the system journal for the corresponding local-time interval
returned no entries that explained the activity. This does not establish
whether the activity was benign or malicious, and the system-wide disk metric
does not identify the responsible process.

The evaluator reproduced the same result on subsequent execution.

## 7. Earlier public-dataset benchmark

The exploratory SMD benchmark is implemented in `ml/p15_smd_benchmark.py`.
The recorded experiment results are in `ml/p15_experiment_results.csv`.

The exploratory run reported approximately:

- F1: 0.67
- ROC-AUC: 0.946
- Average precision: 0.6405

Feature selection was influenced by test-label results, so these metrics are
selection-biased and must not be presented as an unbiased final benchmark.
They are exploratory evidence only and are not comparable directly with the
unlabelled live-telemetry evaluation.

## 8. Limitations

- Live telemetry has no ground-truth anomaly labels.
- The collected normal-use period is not guaranteed to be anomaly-free.
- A flagged observation is an anomaly candidate, not a confirmed incident.
- The calibration threshold does not guarantee future alert or false-positive
  rates.
- Collection interruptions and the selected training period affect the
  evidence available for evaluation.
- The unseen evaluation is small and comes from one host and one time period.
- The detector should be evaluated further as more representative telemetry
  becomes available.

## 9. Reproduction

From the repository root, with the project's Python virtual environment
activated:

Collect new telemetry while the monitoring stack is running:

```bash
python ml/p15_collect_telemetry.py
```

Evaluate using the existing model and fixed threshold, without retraining:

```bash
python ml/p15_evaluate_live.py
```

Retraining is a separate operation that overwrites the v2 model and metadata:

```bash
python ml/p15_train_live_v2.py
```

Do not retrain when reproducing the recorded unseen evaluation. Preserve the
existing model, metadata, and threshold. If retraining uses the evaluation
period, collect a new, later period for independent evaluation.

## 10. P15 outcome

The v2 Isolation Forest baseline, saved threshold, and reusable unseen-data
evaluator are implemented. The recorded evaluation is reproducible on the
available local CSV.

The detector remains an exploratory baseline rather than a validated
production detector. The next milestone, P16, will visualize anomaly scores,
flagged periods, and supporting telemetry in Grafana.
