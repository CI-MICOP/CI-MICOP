"""Evaluates the rule-based baseline and both ML models on exactly the
same test claims, with imbalance-aware metrics (Step 5.2, Section 9-11).
Accuracy is computed but never treated as the headline number.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display available / needed - just save PNGs
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.metrics import accuracy_score as _accuracy_score


def evaluate_binary(y_true, y_pred, y_score=None) -> dict:
    """y_true/y_pred are 0/1 arrays. y_score (probability or continuous
    risk score) is optional - ROC-AUC/PR-AUC are only computed when both
    classes are present in y_true AND a score was supplied; otherwise
    they are reported as None rather than a fabricated number."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    metrics = {
        "accuracy": float(_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": None,
        "pr_auc": None,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "n_test": int(len(y_true)),
        "n_positive_actual": int(y_true.sum()),
        "n_positive_predicted": int(y_pred.sum()),
    }

    single_class_test = len(np.unique(y_true)) < 2
    if single_class_test:
        metrics["note"] = "ROC-AUC/PR-AUC not computed: the test split contains only one class."
    elif y_score is not None:
        y_score = np.asarray(y_score)
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_score))
        metrics["pr_auc"] = float(average_precision_score(y_true, y_score))
    else:
        metrics["note"] = "ROC-AUC/PR-AUC not computed: no continuous score was supplied for this approach."

    return metrics


def format_metrics_report(name: str, metrics: dict) -> str:
    lines = [f"--- {name} ---"]
    lines.append(f"  n_test={metrics['n_test']}  actual_positives={metrics['n_positive_actual']}  predicted_positives={metrics['n_positive_predicted']}")
    lines.append(f"  Accuracy:  {metrics['accuracy']:.3f}  (reported for completeness, NOT the headline metric - see PR-AUC/Recall)")
    lines.append(f"  Precision: {metrics['precision']:.3f}")
    lines.append(f"  Recall:    {metrics['recall']:.3f}")
    lines.append(f"  F1:        {metrics['f1']:.3f}")
    roc = metrics["roc_auc"]
    pr = metrics["pr_auc"]
    lines.append(f"  ROC-AUC:   {roc:.3f}" if roc is not None else f"  ROC-AUC:   N/A ({metrics.get('note', '')})")
    lines.append(f"  PR-AUC:    {pr:.3f}" if pr is not None else f"  PR-AUC:    N/A ({metrics.get('note', '')})")
    cm = metrics["confusion_matrix"]
    lines.append(f"  Confusion matrix [ [TN={cm[0][0]}, FP={cm[0][1]}], [FN={cm[1][0]}, TP={cm[1][1]}] ]")
    return "\n".join(lines)


def save_confusion_matrix_plot(metrics: dict, title: str, save_path: Path) -> None:
    """Plain, unstyled confusion-matrix plot with TN/FP/FN/TP labeled."""
    cm = np.array(metrics["confusion_matrix"])
    display = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["Not Fraud", "Fraud"])
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    display.plot(ax=ax, colorbar=False)
    ax.set_title(title)
    # Overlay TN/FP/FN/TP labels under the sklearn-drawn counts.
    labels = [["TN", "FP"], ["FN", "TP"]]
    for i in range(2):
        for j in range(2):
            ax.text(j, i + 0.22, labels[i][j], ha="center", va="center", fontsize=9, color="gray")
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
