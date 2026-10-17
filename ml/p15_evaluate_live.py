import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

DATA_FILE = Path("data/telemetry/live_metrics.csv")
MODEL_FILE = Path("models/p15_live_isolation_forest_v2.joblib")
METADATA_FILE = Path("models/p15_live_metadata_v2.json")

FEATURES = [
    "cpu_usage_pct",
    "memory_usage_pct",
    "disk_write_bytes_per_second",
    "network_receive_bytes_per_second",
    "load1",
]


def main():
    for path in (DATA_FILE, MODEL_FILE, METADATA_FILE):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    metadata = json.loads(METADATA_FILE.read_text())
    if metadata.get("features") != FEATURES:
        raise ValueError("Model metadata feature order does not match.")

    threshold = float(metadata["anomaly_threshold_on_score_samples"])
    calibration_end = pd.to_datetime(
        metadata["calibration_end_utc"], utc=True
    )

    df = pd.read_csv(DATA_FILE)

    required_columns = {"timestamp", *FEATURES}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], utc=True, errors="coerce"
    )
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    df = df[df["timestamp"] > calibration_end].copy()

    if df.empty:
        print("No telemetry samples found after the calibration period.")
        return

    values = df[FEATURES].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Evaluation data contains non-finite feature values.")

    model = joblib.load(MODEL_FILE)
    scores = model.score_samples(values)
    df["anomaly_score"] = scores
    df["is_anomaly_candidate"] = scores < threshold

    flagged = df[df["is_anomaly_candidate"]]

    print("P15 live Isolation Forest evaluation")
    print(f"Model version: {metadata.get('version', 'unknown')}")
    print(f"Calibration ended (UTC): {calibration_end}")
    print(f"Evaluation samples: {len(df)}")
    print(f"Threshold: {threshold:.12f}")
    print(
        f"Flagged samples: {len(flagged)} "
        f"({len(flagged) / len(df):.2%})"
    )
    print(f"Score min: {scores.min():.6f}")
    print(f"Score mean: {scores.mean():.6f}")
    print(f"Score max: {scores.max():.6f}")
    print(f"Evaluation start (UTC): {df['timestamp'].min()}")
    print(f"Evaluation end (UTC): {df['timestamp'].max()}")

    if flagged.empty:
        print("\nNo anomaly candidates flagged.")
    else:
        print("\nFlagged observations:")
        for _, row in flagged.iterrows():
            features = " | ".join(
                f"{feature}={row[feature]:.3f}"
                for feature in FEATURES
            )
            print(
                f"{row['timestamp'].isoformat()} | "
                f"score={row['anomaly_score']:.6f} | {features}"
            )

    print(
        "\nInterpretation: flagged observations are anomaly candidates, "
        "not confirmed incidents. No live ground-truth labels are available."
    )


if __name__ == "__main__":
    main()
