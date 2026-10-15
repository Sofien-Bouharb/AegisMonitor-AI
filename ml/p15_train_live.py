import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DATA_FILE = Path("data/telemetry/live_metrics.csv")
MODEL_DIR = Path("models")
MODEL_FILE = MODEL_DIR / "p15_live_isolation_forest.joblib"
METADATA_FILE = MODEL_DIR / "p15_live_metadata.json"

SEED = 42
FIT_RATIO = 0.80
TARGET_VALIDATION_FPR = 0.01

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

    # Exclude the four initial test samples before the long collection session.
    df = df.iloc[4:].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    if df[FEATURES].isna().any().any():
        raise ValueError("Telemetry contains missing feature values.")

    values = df[FEATURES].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Telemetry contains non-finite feature values.")

    split = int(len(df) * FIT_RATIO)
    fit_df = df.iloc[:split]
    validation_df = df.iloc[split:]

    X_fit = values[:split]
    X_validation = values[split:]

    if len(X_fit) < 100 or len(X_validation) < 20:
        raise ValueError("Not enough samples for a meaningful initial split.")

    model = IsolationForest(
        n_estimators=200,
        max_samples="auto",
        contamination="auto",
        random_state=SEED,
        n_jobs=-1,
    )
    model.fit(X_fit)

    # Lower score_samples values indicate more anomalous observations.
    fit_scores = model.score_samples(X_fit)
    validation_scores = model.score_samples(X_validation)
    threshold = float(np.quantile(validation_scores, TARGET_VALIDATION_FPR))

    validation_predictions = validation_scores < threshold

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_FILE)

    metadata = {
        "model": "IsolationForest",
        "features": FEATURES,
        "random_state": SEED,
        "n_estimators": 200,
        "max_samples": "auto",
        "contamination": "auto",
        "fit_samples": len(X_fit),
        "validation_samples": len(X_validation),
        "fit_start_utc": fit_df["timestamp"].iloc[0].isoformat(),
        "fit_end_utc": fit_df["timestamp"].iloc[-1].isoformat(),
        "validation_start_utc": validation_df["timestamp"].iloc[0].isoformat(),
        "validation_end_utc": validation_df["timestamp"].iloc[-1].isoformat(),
        "target_validation_tail_fraction": TARGET_VALIDATION_FPR,
        "anomaly_threshold_on_score_samples": threshold,
        "validation_flagged": int(validation_predictions.sum()),
        "validation_flagged_fraction": float(validation_predictions.mean()),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Initial baseline trained on mostly idle live telemetry. "
            "Validation threshold is not proof of a 1% future false-positive rate. "
            "No ground-truth live anomaly labels are available."
        ),
    }

    METADATA_FILE.write_text(json.dumps(metadata, indent=2) + "\n")

    print("Initial live Isolation Forest training complete.")
    print(f"Samples: {len(df)}")
    print(f"Fit samples: {len(X_fit)}")
    print(f"Validation samples: {len(X_validation)}")
    print(f"Fit score mean: {fit_scores.mean():.6f}")
    print(f"Validation score mean: {validation_scores.mean():.6f}")
    print(f"Score threshold: {threshold:.6f}")
    print(
        f"Validation flagged: {int(validation_predictions.sum())} "
        f"({validation_predictions.mean():.2%})"
    )
    print(f"Model saved: {MODEL_FILE}")
    print(f"Metadata saved: {METADATA_FILE}")


if __name__ == "__main__":
    main()
