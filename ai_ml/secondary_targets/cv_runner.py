"""Runs Logistic Regression / Random Forest (and, where applicable, a rule
baseline) through repeated Customer_ID-grouped cross-validation for one
target, reusing Step 5.2's preprocessing/model-building code
(`ai_ml.models.train_fraud_models`) unchanged. One row per (seed, fold,
model) is returned so `validation.summarize_stability` can be applied
per model afterward.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)

from ai_ml.models.train_fraud_models import (
    build_preprocessor,
    classify_feature_columns,
    train_logistic_regression,
    train_random_forest,
)
from ai_ml.secondary_targets.validation import RANDOM_SEEDS, choose_fold_count, make_folds

warnings.filterwarnings("ignore", category=ConvergenceWarning)


def _fit_predict(model_name: str, X_train, y_train, X_val, numeric_cols, categorical_cols, class_weight):
    preprocessor = build_preprocessor(numeric_cols, categorical_cols)
    if model_name == "logistic_regression":
        pipeline = train_logistic_regression(X_train, y_train, preprocessor, class_weight=class_weight)
    elif model_name == "random_forest":
        pipeline = train_random_forest(X_train, y_train, preprocessor, class_weight=class_weight)
    else:
        raise ValueError(model_name)
    return pipeline, pipeline.predict(X_val), pipeline.predict_proba(X_val)


def run_binary_cv(df: pd.DataFrame, target: str, safe_cols: list[str], model_names=("logistic_regression", "random_forest"), max_folds: int = 5, seeds=RANDOM_SEEDS) -> pd.DataFrame:
    y_all = df[target].astype(int)
    min_class_size = int(y_all.value_counts().min())
    n_splits = choose_fold_count(min_class_size, max_folds=max_folds)
    if n_splits == 0:
        return pd.DataFrame(), {"skipped": True, "reason": f"smallest class has only {min_class_size} rows - too few for reliable folds."}

    report = classify_feature_columns(df, safe_cols)
    numeric_cols, categorical_cols = report["numeric"], report["categorical"]
    feature_cols = numeric_cols + categorical_cols

    rows = []
    for seed in seeds:
        folds = make_folds(df, target, n_splits, seed)
        for fold_i, (train_idx, val_idx) in enumerate(folds):
            X_train, X_val = df.iloc[train_idx][feature_cols], df.iloc[val_idx][feature_cols]
            y_train, y_val = y_all.iloc[train_idx], y_all.iloc[val_idx]
            class_weight = "balanced" if y_train.mean() < 0.4 or y_train.mean() > 0.6 else None

            for model_name in model_names:
                _, y_pred, proba = _fit_predict(model_name, X_train, y_train, X_val, numeric_cols, categorical_cols, class_weight)
                y_score = proba[:, 1]
                single_class_val = y_val.nunique() < 2
                roc_auc = None if single_class_val else float(roc_auc_score(y_val, y_score))
                pr_auc = None if single_class_val else float(average_precision_score(y_val, y_score))
                rows.append({
                    "target": target, "model": model_name, "seed": seed, "fold": fold_i,
                    "n_train": len(train_idx), "n_val": len(val_idx),
                    "accuracy": float(accuracy_score(y_val, y_pred)),
                    "precision": float(precision_recall_fscore_support(y_val, y_pred, average="binary", zero_division=0)[0]),
                    "recall": float(precision_recall_fscore_support(y_val, y_pred, average="binary", zero_division=0)[1]),
                    "f1": float(f1_score(y_val, y_pred, zero_division=0)),
                    "roc_auc": roc_auc,
                    "pr_auc": pr_auc,
                })
    return pd.DataFrame(rows), {"skipped": False, "n_splits": n_splits, "n_repeats": len(seeds), "min_class_size": min_class_size}


def run_multiclass_cv(df: pd.DataFrame, target: str, safe_cols: list[str], model_names=("logistic_regression", "random_forest"), max_folds: int = 5, seeds=RANDOM_SEEDS) -> pd.DataFrame:
    y_all = df[target].astype(str)
    class_counts = y_all.value_counts()
    n_classes = class_counts.shape[0]
    min_class_size = int(class_counts.min())
    n_splits = choose_fold_count(min_class_size, max_folds=max_folds)
    if n_splits == 0:
        return pd.DataFrame(), {"skipped": True, "reason": f"smallest class has only {min_class_size} rows - too few for reliable folds."}

    report = classify_feature_columns(df, safe_cols)
    numeric_cols, categorical_cols = report["numeric"], report["categorical"]
    feature_cols = numeric_cols + categorical_cols

    rows = []
    for seed in seeds:
        folds = make_folds(df, target, n_splits, seed)
        for fold_i, (train_idx, val_idx) in enumerate(folds):
            X_train, X_val = df.iloc[train_idx][feature_cols], df.iloc[val_idx][feature_cols]
            y_train, y_val = y_all.iloc[train_idx], y_all.iloc[val_idx]

            for model_name in model_names:
                pipeline, y_pred, proba = _fit_predict(model_name, X_train, y_train, X_val, numeric_cols, categorical_cols, "balanced")
                precision, recall, f1_macro, _ = precision_recall_fscore_support(y_val, y_pred, average="macro", zero_division=0)
                _, _, f1_weighted, _ = precision_recall_fscore_support(y_val, y_pred, average="weighted", zero_division=0)

                roc_auc_macro = None
                if set(y_val.unique()) == set(pipeline.classes_) and n_classes > 1:
                    try:
                        roc_auc_macro = float(roc_auc_score(y_val, proba, multi_class="ovr", average="macro", labels=pipeline.classes_))
                    except ValueError:
                        roc_auc_macro = None

                rows.append({
                    "target": target, "model": model_name, "seed": seed, "fold": fold_i,
                    "n_train": len(train_idx), "n_val": len(val_idx),
                    "accuracy": float(accuracy_score(y_val, y_pred)),
                    "macro_precision": float(precision),
                    "macro_recall": float(recall),
                    "macro_f1": float(f1_macro),
                    "weighted_f1": float(f1_weighted),
                    "roc_auc_ovr_macro": roc_auc_macro,
                })
    return pd.DataFrame(rows), {"skipped": False, "n_splits": n_splits, "n_repeats": len(seeds), "min_class_size": min_class_size, "n_classes": n_classes}


def run_rule_baseline_cv(df: pd.DataFrame, target: str, screener_factory, model_label: str, max_folds: int = 5, seeds=RANDOM_SEEDS) -> pd.DataFrame:
    """Same repeated grouped-CV protocol as `run_binary_cv`, but for a
    rule-based screener with a `.fit(train_df)` / `.predict(df)`
    interface (both `RuleBasedFraudScreener` and
    `ExcessiveAmountRuleScreener` implement it) instead of a scikit-learn
    Pipeline. The screener is re-fit (thresholds recalibrated) on each
    fold's TRAINING portion only - never on its validation portion."""
    y_all = df[target].astype(int)
    min_class_size = int(y_all.value_counts().min())
    n_splits = choose_fold_count(min_class_size, max_folds=max_folds)
    if n_splits == 0:
        return pd.DataFrame(), {"skipped": True, "reason": f"smallest class has only {min_class_size} rows - too few for reliable folds."}

    rows = []
    for seed in seeds:
        folds = make_folds(df, target, n_splits, seed)
        for fold_i, (train_idx, val_idx) in enumerate(folds):
            train_df, val_df = df.iloc[train_idx], df.iloc[val_idx]
            screener = screener_factory()
            screener.fit(train_df)
            predictions = screener.predict(val_df)
            y_val = y_all.iloc[val_idx].values
            y_pred = predictions["Rule_Baseline_Prediction"].values
            y_score = predictions["Rule_Baseline_Score"].values
            single_class_val = len(set(y_val)) < 2
            roc_auc = None if single_class_val else float(roc_auc_score(y_val, y_score))
            pr_auc = None if single_class_val else float(average_precision_score(y_val, y_score))
            rows.append({
                "target": target, "model": model_label, "seed": seed, "fold": fold_i,
                "n_train": len(train_idx), "n_val": len(val_idx),
                "accuracy": float(accuracy_score(y_val, y_pred)),
                "precision": float(precision_recall_fscore_support(y_val, y_pred, average="binary", zero_division=0)[0]),
                "recall": float(precision_recall_fscore_support(y_val, y_pred, average="binary", zero_division=0)[1]),
                "f1": float(f1_score(y_val, y_pred, zero_division=0)),
                "roc_auc": roc_auc,
                "pr_auc": pr_auc,
            })
    return pd.DataFrame(rows), {"skipped": False, "n_splits": n_splits, "n_repeats": len(seeds), "min_class_size": min_class_size}
