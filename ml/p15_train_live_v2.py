
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DATA_FILE = Path("data/telemetry/live_metrics.csv")
MODEL_DIR = Path("models")
MODEL_FILE = MODEL_DIR / "p15_live_isolation_forest_v2.joblib"
METADATA_FILE = MODEL_DIR / "p15_live_metadata_v2.json"

SEED = 42
FIT_RATIO = 0.80
TARGET_VALIDATION_TAIL_FRACTION = 0.01
MAX_COLLECTION_GAP_SECONDS = 60

FEATURES = [
    "cpu_usage_pct",
    "memory_usage_pct",
    "disk_write_bytes_per_second",
    "network_receive_bytes_per_second",
    "load1",
]


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Telemetry file not found: {DATA_FILE}")

    df = pd.read_csv(DATA_FILE)

    missing_columns = {"timestamp", *FEATURES} - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing columns: {sorted(missing_columns)}")

    # Exclude the four initial test samples before the overnight session.
    df = df.iloc[4:].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Keep only the newer normal-use collection period.
    # The first 1,933 rows after the initial four samples belong to v1.
    df = df.iloc[1933:].reset_index(drop=True)

    if len(df) < 100:
        raise ValueError(
            f"Not enough newer telemetry samples: {len(df)}"
        )

    if df["timestamp"].isna().any():
        raise ValueError("Telemetry contains invalid timestamps.")

    if df["timestamp"].duplicated().any():
        raise ValueError("Telemetry contains duplicate timestamps.")

    if df[FEATURES].isna().any().any():
        raise ValueError("Telemetry contains missing feature values.")

    values = df[FEATURES].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Telemetry contains non-finite feature values.")

    if (df["timestamp"].diff().dt.total_seconds().dropna() <= 0).any():
        raise ValueError("Timestamps must be strictly increasing.")

    split = int(len(df) * FIT_RATIO)
    fit_df = df.iloc[:split].copy()
    calibration_df = df.iloc[split:].copy()

    X_fit = values[:split]
    X_calibration = values[split:]

    model = IsolationForest(
        n_estimators=200,
        max_samples="auto",
        contamination="auto",
        random_state=SEED,
        n_jobs=-1,
    )
    model.fit(X_fit)

    # Lower score_samples values indicate more anomalous observations.
    calibration_scores = model.score_samples(X_calibration)
    threshold = float(
        np.quantile(
            calibration_scores,
            TARGET_VALIDATION_TAIL_FRACTION,
        )
    )
    calibration_predictions = calibration_scores < threshold

    # Record interruptions; do not treat missing time as observed telemetry.
    gaps = df["timestamp"].diff().dt.total_seconds().dropna()
    large_gaps = gaps[gaps > MAX_COLLECTION_GAP_SECONDS]

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_FILE)

    metadata = {
        "model": "IsolationForest",
        "version": 2,
        "features": FEATURES,
        "random_state": SEED,
        "n_estimators": 200,
        "max_samples": "auto",
        "contamination": "auto",
        "dataset": str(DATA_FILE),
        "dataset_description": (
            "Newer live telemetry collected during normal laptop use; "
            "not independently verified as entirely anomaly-free."
        ),
        "excluded_initial_samples": 4,
        "excluded_original_baseline_samples": 1933,
        "total_candidate_samples": len(df),
        "fit_samples": len(X_fit),
        "calibration_samples": len(X_calibration),
        "fit_start_utc": fit_df["timestamp"].iloc[0].isoformat(),
        "fit_end_utc": fit_df["timestamp"].iloc[-1].isoformat(),
        "calibration_start_utc": (
            calibration_df["timestamp"].iloc[0].isoformat()
        ),
        "calibration_end_utc": (
            calibration_df["timestamp"].iloc[-1].isoformat()
        ),
        "target_calibration_tail_fraction": (
            TARGET_VALIDATION_TAIL_FRACTION
        ),
        "anomaly_threshold_on_score_samples": threshold,
        "calibration_flagged": int(calibration_predictions.sum()),
        "calibration_flagged_fraction": float(
            calibration_predictions.mean()
        ),
        "collection_gaps_over_60_seconds": int(len(large_gaps)),
        "largest_collection_gap_seconds": (
            float(gaps.max()) if len(gaps) else 0.0
        ),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Exploratory v2 baseline trained on newer telemetry from "
            "normal laptop use. Normal-use data is not guaranteed to be "
            "free of anomalies. Calibration uses the final chronological "
            "20% of this dataset; its tail fraction does not establish "
            "a future false-positive rate. Collection was interrupted, "
            "and no ground-truth live anomaly labels are available. "
            "Compare with v1 and review flagged events before deployment."
        ),
    }

    METADATA_FILE.write_text(json.dumps(metadata, indent=2) + "\n")

    print("Exploratory live Isolation Forest v2 training complete.")
    print(f"Candidate samples: {len(df)}")
    print(f"Fit samples: {len(X_fit)}")
    print(f"Calibration samples: {len(X_calibration)}")
    print(f"Fit period: {metadata['fit_start_utc']} to {metadata['fit_end_utc']}")
    print(
        "Calibration period: "
        f"{metadata['calibration_start_utc']} to "
        f"{metadata['calibration_end_utc']}"
    )
    print(f"Calibration score mean: {calibration_scores.mean():.6f}")
    print(f"Score threshold: {threshold:.6f}")
    print(
        f"Calibration flagged: {int(calibration_predictions.sum())} "
        f"({calibration_predictions.mean():.2%})"
    )
    print(f"Gaps > 60 seconds: {len(large_gaps)}")
    print(f"Model saved: {MODEL_FILE}")
    print(f"Metadata saved: {METADATA_FILE}")
    print("Note: calibration is not proof of a 1% future false-positive rate.")


if __name__ == "__main__":
    main()
