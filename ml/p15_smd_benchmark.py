import csv
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

DATA_DIR = Path("data/smd/machine-1-1")
SEED = 42
FIT_RATIO = 0.80
TARGET_VALIDATION_FPR = 0.01

# Zero-based indices selected for the AegisMonitor feature subset.
AEGIS_FEATURES = {
    0: "cpu_r",
    1: "load_1",
    5: "mem_u",
    10: "disk_rb",
    15: "disk_wb",
    18: "eth1_fi",
    19: "eth1_fo",
}


def load_matrix(path):
    with path.open(newline="") as file:
        data = [
            [float(value) for value in row]
            for row in csv.reader(file)
            if row and any(value.strip() for value in row)
        ]

    array = np.asarray(data, dtype=float)

    if array.ndim != 2 or not np.isfinite(array).all():
        raise ValueError(f"Invalid or non-finite data in {path}")

    return array


def evaluate(name, train, test, labels, selected_indices):
    # Chronological split: earlier observations fit the model;
    # the training tail is reserved for threshold selection.
    split = int(len(train) * FIT_RATIO)
    fit_data = train[:split]
    validation_data = train[split:]

    # Remove features constant in the fitting segment only.
    variable_mask = np.ptp(fit_data[:, selected_indices], axis=0) > 0
    usable_indices = np.asarray(selected_indices)[variable_mask]

    if len(usable_indices) == 0:
        raise ValueError(f"{name}: no variable features remain")

    X_fit = fit_data[:, usable_indices]
    X_validation = validation_data[:, usable_indices]
    X_test = test[:, usable_indices]

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
    test_scores = model.score_samples(X_test)
   
    # Threshold uses training-tail scores, never test labels.
    threshold = np.quantile(
        validation_scores, TARGET_VALIDATION_FPR
    )

    print("\nScore distribution diagnostics (lower = more anomalous):")

    for split_name, scores in [
        ("Fit", fit_scores),
        ("Validation", validation_scores),
        ("Test", test_scores),
    ]:
        print(
            f"  {split_name:10} "
            f"min={np.min(scores):.4f} "
            f"p01={np.quantile(scores, 0.01):.4f} "
            f"median={np.median(scores):.4f} "
            f"p99={np.quantile(scores, 0.99):.4f} "
            f"max={np.max(scores):.4f} "
            f"below_threshold={np.mean(scores < threshold):.2%}"
        )

    predictions = (test_scores < threshold).astype(int)

    roc_auc = roc_auc_score(labels, -test_scores)
    average_precision = average_precision_score(labels, -test_scores)
    precision = precision_score(labels, predictions, zero_division=0)
    recall = recall_score(labels, predictions, zero_division=0)
    f1 = f1_score(labels, predictions, zero_division=0)

    print(f"\n{'=' * 60}")
    print(name)
    print(f"{'=' * 60}")
    print(f"Fit observations:       {len(X_fit)}")
    print(f"Validation observations:{len(X_validation):>7}")
    print(f"Test observations:      {len(X_test)}")
    print(f"Selected features used: {len(usable_indices)}")
    print(f"Feature indices:        {usable_indices.tolist()}")
    print(f"Score threshold:        {threshold:.6f}")
    print(f"ROC-AUC:                {roc_auc:.4f}")
    print(f"Average precision:      {average_precision:.4f}")
    print(f"Precision:              {precision:.4f}")
    print(f"Recall:                 {recall:.4f}")
    print(f"F1:                     {f1:.4f}")
    print("Confusion matrix [normal, anomaly]:")
    print(confusion_matrix(labels, predictions, labels=[0, 1]))


def main():
    train = load_matrix(DATA_DIR / "train.txt")
    test = load_matrix(DATA_DIR / "test.txt")
    labels_matrix = load_matrix(DATA_DIR / "test_label.txt")

    labels = labels_matrix.ravel().astype(int)

    if train.shape[1] != 38 or test.shape[1] != 38:
        raise ValueError("Expected 38 SMD features")
    if len(test) != len(labels):
        raise ValueError("Test observations and labels do not align")
    if not np.isin(labels, [0, 1]).all():
        raise ValueError("Expected binary labels 0 and 1")

    all_indices = list(range(train.shape[1]))
    aegis_indices = list(AEGIS_FEATURES.keys())

    evaluate(
        "Experiment A — all SMD features",
        train, test, labels, all_indices
    )
    evaluate(
        "Experiment B — AegisMonitor feature subset",
        train, test, labels, aegis_indices
    )


if __name__ == "__main__":
    main()