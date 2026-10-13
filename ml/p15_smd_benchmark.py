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



FEATURE_EXPERIMENTS = {
    "CPU only": [0],
    "Load only": [1],
    "Memory only": [5],
    "Disk read only": [10],
    "Disk write only": [15],
    "Network receive only": [18],
    "Network transmit only": [19],

    "CPU + load": [0, 1],
    "CPU + memory": [0, 5],
    "CPU + load + memory": [0, 1, 5],
    "CPU + disk read": [0, 10],
    "CPU + disk write": [0, 15],
    "CPU + disk read + write": [0, 10, 15],
    "CPU + network receive": [0, 18],
    "CPU + network transmit": [0, 19],
    "CPU + network receive + transmit": [0, 18, 19],

    "All AegisMonitor features": [0, 1, 5, 10, 15, 18, 19],
    "All variable features": list(range(38)),
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


    if name == "Experiment B — AegisMonitor feature subset":
        print("\nFeature distribution diagnostics (median, p10, p90):")

        for column, feature_index in enumerate(usable_indices):
            feature_name = AEGIS_FEATURES[int(feature_index)]

            fit_values = X_fit[:, column]
            validation_values = X_validation[:, column]
            test_values = X_test[:, column]
            normal_test = test_values[labels == 0]
            anomaly_test = test_values[labels == 1]

            def summary(values):
                return (
                    f"median={np.median(values):.4f}, "
                    f"p10={np.quantile(values, 0.10):.4f}, "
                    f"p90={np.quantile(values, 0.90):.4f}"
                )

            print(f"\n  {feature_name}:")
            print(f"    Fit:           {summary(fit_values)}")
            print(f"    Validation:    {summary(validation_values)}")
            print(f"    Test (all):    {summary(test_values)}")
            print(f"    Test (normal): {summary(normal_test)}")
            print(f"    Test (anomaly): {summary(anomaly_test)}")



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

    return {
        "experiment": name,
        "features": ",".join(
            AEGIS_FEATURES.get(int(index), str(index))
            for index in usable_indices
        ),
        "feature_count": len(usable_indices),
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "threshold": threshold,
        "false_positives": int(
            confusion_matrix(labels, predictions, labels=[0, 1])[0, 1]
        ),
        "false_negatives": int(
            confusion_matrix(labels, predictions, labels=[0, 1])[1, 0]
        ),
    }

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

    results = []

    for experiment_name, feature_indices in FEATURE_EXPERIMENTS.items():
        result = evaluate(
            experiment_name, train, test, labels, feature_indices
        )
        results.append(result)

    print("\n\n" + "=" * 100)
    print("EXPERIMENT SUMMARY")
    print("=" * 100)

    print(
        f"{'Experiment':<38}"
        f"{'ROC-AUC':>10}"
        f"{'Avg Prec.':>12}"
        f"{'Precision':>12}"
        f"{'Recall':>10}"
        f"{'F1':>10}"
    )

    for result in results:
        print(
            f"{result['experiment']:<38}"
            f"{result['roc_auc']:>10.4f}"
            f"{result['average_precision']:>12.4f}"
            f"{result['precision']:>12.4f}"
            f"{result['recall']:>10.4f}"
            f"{result['f1']:>10.4f}"
        )

    best_result = max(results, key=lambda result: result["f1"])
    print(f"\nBest F1: {best_result['experiment']} ({best_result['f1']:.4f})")

    results_path = Path("ml/p15_experiment_results.csv")

    with results_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    main()