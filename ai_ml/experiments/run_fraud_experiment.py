"""Step 5.2 experiment: Rule-Based Baseline vs. ML (Logistic Regression,
Random Forest) for `frd_Fraud_Label`, on the same customer-grouped test
set, with SHAP + reason-code explanations.

Run from the repo root:
    python -m ai_ml.experiments.run_fraud_experiment

This is a validation study on CI-MICOP's current synthetic/de-identified
dataset (see docs/project_documentation/AI_ML_DATASET_AUDIT.md). Nothing
here should be read as production fraud-detection performance.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener
from ai_ml.common.feature_builder import (
    build_claim_level_dataset,
    leaked_columns_for_target,
    safe_feature_columns,
)
from ai_ml.explainability.reason_codes import build_claim_explanation
from ai_ml.explainability.shap_explainer import explain_claims, risk_level_from_probability, to_reason_codes
from ai_ml.models.evaluation import evaluate_binary, format_metrics_report, save_confusion_matrix_plot
from ai_ml.models.train_fraud_models import (
    add_engineered_features,
    build_preprocessor,
    classify_feature_columns,
    train_logistic_regression,
    train_random_forest,
)

TARGET = "frd_Fraud_Label"
RANDOM_SEED = 42
ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "model_artifacts"

EXPLANATORY_COLUMNS_FOR_ERROR_ANALYSIS = [
    "Claim_Type", "Claim_Amount", "cdc_Overall_Consistency_Status",
    "est_Excessive_Claim_Amount_Indicator", "evidence_any_duplicate_flag",
    "document_completeness_mean", "repair_ratio", "days_since_policy_start",
]


def load_and_validate() -> pd.DataFrame:
    df = build_claim_level_dataset()
    df = add_engineered_features(df)

    if TARGET not in df.columns:
        raise ValueError(f"Target column '{TARGET}' is missing from the claim-level dataset.")
    if df["Claim_ID"].duplicated().any():
        raise AssertionError("Claim_ID is duplicated in the claim-level dataset - refusing to proceed.")

    unique_labels = set(df[TARGET].dropna().unique().tolist())
    if not unique_labels.issubset({0, 1}):
        raise ValueError(f"Target '{TARGET}' is not binary (found values: {unique_labels}).")

    counts = df[TARGET].value_counts().sort_index()
    pct = (counts / len(df) * 100).round(2)
    print("=" * 100)
    print(f"TARGET VALIDATION: {TARGET}")
    print("=" * 100)
    print(f"Claims: {len(df)}  |  Claim_ID unique: True  |  Binary target: True")
    for label in [0, 1]:
        print(f"  class {label}: {counts.get(label, 0)} ({pct.get(label, 0.0)}%)")

    return df


def create_grouped_split(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_SEED)
    train_idx, test_idx = next(splitter.split(df, groups=df["Customer_ID"]))

    train_customers = set(df.iloc[train_idx]["Customer_ID"])
    test_customers = set(df.iloc[test_idx]["Customer_ID"])
    overlap = train_customers & test_customers
    train_claim_ids = set(df.iloc[train_idx]["Claim_ID"])
    test_claim_ids = set(df.iloc[test_idx]["Claim_ID"])

    print()
    print("=" * 100)
    print("CUSTOMER-GROUPED TRAIN/TEST SPLIT")
    print("=" * 100)
    print(f"train claims:    {len(train_idx)}   train customers: {len(train_customers)}")
    print(f"test claims:     {len(test_idx)}   test customers:  {len(test_customers)}")
    print(f"overlapping customers: {len(overlap)}")
    train_pct = df.iloc[train_idx][TARGET].mean() * 100
    test_pct = df.iloc[test_idx][TARGET].mean() * 100
    print(f"train positive rate: {train_pct:.2f}%   test positive rate: {test_pct:.2f}%")

    if overlap:
        raise AssertionError(f"Customer leakage across train/test: {len(overlap)} customers appear in both splits.")
    if train_claim_ids & test_claim_ids:
        raise AssertionError("Claim_ID overlap between train and test splits.")

    return train_idx, test_idx


def run_rule_baseline(df: pd.DataFrame, train_idx: np.ndarray, test_idx: np.ndarray) -> tuple[pd.DataFrame, dict]:
    screener = RuleBasedFraudScreener()
    screener.fit(df.iloc[train_idx])
    predictions = screener.predict(df.iloc[test_idx])
    calibration = screener.calibration_summary()

    print()
    print("=" * 100)
    print("RULE-BASED BASELINE - calibrated on TRAINING data only")
    print("=" * 100)
    for key, value in calibration.items():
        print(f"  {key}: {value}")

    return predictions, calibration


def build_ml_feature_sets(df: pd.DataFrame, train_idx: np.ndarray, test_idx: np.ndarray) -> dict:
    safe_cols = safe_feature_columns(TARGET, df)
    report = classify_feature_columns(df, safe_cols)
    numeric_cols, categorical_cols = report["numeric"], report["categorical"]

    leaked = set(leaked_columns_for_target(TARGET, df))
    model_cols = set(numeric_cols) | set(categorical_cols)
    if leaked & model_cols:
        raise AssertionError(f"Leaked columns entered the model feature set: {leaked & model_cols}")

    print()
    print("=" * 100)
    print("MODEL FEATURE SET (on top of feature_builder's leakage exclusions)")
    print("=" * 100)
    print(f"safe (leakage-free) columns from feature_builder: {len(safe_cols)}")
    print(f"  -> numeric features used:      {len(numeric_cols)}")
    print(f"  -> categorical features used:  {len(categorical_cols)}")
    print(f"  -> excluded (direct identifier): {len(report['excluded_identifier'])} -> {report['excluded_identifier']}")
    print(f"  -> excluded (free text):         {len(report['excluded_free_text'])} -> {report['excluded_free_text']}")
    print(f"  -> excluded (high-cardinality categorical, likely near-identifier): {len(report['excluded_high_cardinality'])} -> {report['excluded_high_cardinality']}")
    print(f"  -> excluded (raw datetime, replaced by engineered numeric features): {len(report['excluded_datetime'])}")
    print(f"  -> excluded (zero-information / fully missing): {len(report['excluded_zero_information'])} -> {report['excluded_zero_information']}")

    feature_cols = numeric_cols + categorical_cols
    X_train = df.iloc[train_idx][feature_cols]
    X_test = df.iloc[test_idx][feature_cols]
    y_train = df.iloc[train_idx][TARGET].astype(int)
    y_test = df.iloc[test_idx][TARGET].astype(int)

    return {
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "report": report,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
    }


def select_threshold_from_training_data(df: pd.DataFrame, train_idx: np.ndarray, feature_sets: dict) -> tuple[float, float]:
    """Splits the TRAINING claims (grouped by customer, so no leakage
    even within this inner split) into an inner-train/inner-validation
    set, fits a throwaway model on inner-train, and picks the
    probability threshold that maximizes F1 on inner-validation. The
    test set is never touched by this procedure."""
    inner_splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_SEED)
    train_df = df.iloc[train_idx]
    inner_train_idx, inner_val_idx = next(inner_splitter.split(train_df, groups=train_df["Customer_ID"]))

    X_inner_train = feature_sets["X_train"].iloc[inner_train_idx]
    y_inner_train = feature_sets["y_train"].iloc[inner_train_idx]
    X_inner_val = feature_sets["X_train"].iloc[inner_val_idx]
    y_inner_val = feature_sets["y_train"].iloc[inner_val_idx]

    preprocessor = build_preprocessor(feature_sets["numeric_cols"], feature_sets["categorical_cols"])
    throwaway_model = train_random_forest(X_inner_train, y_inner_train, preprocessor, class_weight="balanced")
    val_proba = throwaway_model.predict_proba(X_inner_val)[:, 1]

    from sklearn.metrics import f1_score

    best_threshold, best_f1 = 0.5, -1.0
    for threshold in np.arange(0.05, 0.96, 0.05):
        f1 = f1_score(y_inner_val, (val_proba >= threshold).astype(int), zero_division=0)
        if f1 > best_f1:
            best_threshold, best_f1 = float(threshold), float(f1)

    print()
    print("=" * 100)
    print("THRESHOLD CALIBRATION (training data only - inner grouped train/validation split)")
    print("=" * 100)
    print(f"inner-train claims: {len(inner_train_idx)}   inner-validation claims: {len(inner_val_idx)}")
    print(f"best threshold by F1 on inner-validation: {best_threshold:.2f} (F1={best_f1:.3f})")
    print("This threshold is then applied to the untouched test set below, alongside the standard 0.5 threshold.")

    return best_threshold, best_f1


def main() -> None:
    df = load_and_validate()
    train_idx, test_idx = create_grouped_split(df)

    rule_predictions, rule_calibration = run_rule_baseline(df, train_idx, test_idx)

    feature_sets = build_ml_feature_sets(df, train_idx, test_idx)
    X_train, X_test = feature_sets["X_train"], feature_sets["X_test"]
    y_train, y_test = feature_sets["y_train"], feature_sets["y_test"]

    train_positive_rate = y_train.mean()
    class_weight = "balanced" if train_positive_rate < 0.4 else None
    print()
    print(f"Training positive rate: {train_positive_rate * 100:.2f}% -> class_weight={class_weight!r}")

    calibrated_threshold, calibrated_f1 = select_threshold_from_training_data(df, train_idx, feature_sets)

    preprocessor_lr = build_preprocessor(feature_sets["numeric_cols"], feature_sets["categorical_cols"])
    preprocessor_rf = build_preprocessor(feature_sets["numeric_cols"], feature_sets["categorical_cols"])
    lr_pipeline = train_logistic_regression(X_train, y_train, preprocessor_lr, class_weight=class_weight)
    rf_pipeline = train_random_forest(X_train, y_train, preprocessor_rf, class_weight=class_weight)

    lr_proba = lr_pipeline.predict_proba(X_test)[:, 1]
    rf_proba = rf_pipeline.predict_proba(X_test)[:, 1]

    results = {
        "rule_baseline": evaluate_binary(y_test, rule_predictions["Rule_Baseline_Prediction"], rule_predictions["Rule_Baseline_Score"]),
        "logistic_regression_0.5": evaluate_binary(y_test, (lr_proba >= 0.5).astype(int), lr_proba),
        "logistic_regression_calibrated": evaluate_binary(y_test, (lr_proba >= calibrated_threshold).astype(int), lr_proba),
        "random_forest_0.5": evaluate_binary(y_test, (rf_proba >= 0.5).astype(int), rf_proba),
        "random_forest_calibrated": evaluate_binary(y_test, (rf_proba >= calibrated_threshold).astype(int), rf_proba),
    }

    print()
    print("=" * 100)
    print("EVALUATION - same test claims for every approach")
    print("=" * 100)
    for name, metrics in results.items():
        print(format_metrics_report(name, metrics))
        print()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    save_confusion_matrix_plot(results["rule_baseline"], "Rule-Based Baseline", ARTIFACT_DIR / "confusion_matrix_rule_baseline.png")
    save_confusion_matrix_plot(results["logistic_regression_0.5"], "Logistic Regression (threshold=0.5)", ARTIFACT_DIR / "confusion_matrix_logistic_regression.png")
    save_confusion_matrix_plot(results["random_forest_0.5"], "Random Forest (threshold=0.5)", ARTIFACT_DIR / "confusion_matrix_random_forest.png")
    print(f"Confusion matrix plots saved under {ARTIFACT_DIR}")

    # ---- False positive / false negative analysis (0.5-threshold predictions) ----
    error_df = df.iloc[test_idx][["Claim_ID"] + EXPLANATORY_COLUMNS_FOR_ERROR_ANALYSIS].copy()
    error_df["actual_fraud_label"] = y_test.values
    error_df = error_df.merge(
        rule_predictions[["Claim_ID", "Rule_Baseline_Prediction", "Rule_Baseline_Score", "Rule_Reason_Codes"]],
        on="Claim_ID", how="left",
    )
    error_df["lr_prediction"] = (lr_proba >= 0.5).astype(int)
    error_df["lr_probability"] = lr_proba
    error_df["rf_prediction"] = (rf_proba >= 0.5).astype(int)
    error_df["rf_probability"] = rf_proba

    def error_subset(pred_col: str, actual_value: int, pred_value: int) -> pd.DataFrame:
        return error_df[(error_df["actual_fraud_label"] == actual_value) & (error_df[pred_col] == pred_value)]

    error_summary = {
        "rule_false_positives": len(error_subset("Rule_Baseline_Prediction", 0, 1)),
        "rule_false_negatives": len(error_subset("Rule_Baseline_Prediction", 1, 0)),
        "lr_false_positives": len(error_subset("lr_prediction", 0, 1)),
        "lr_false_negatives": len(error_subset("lr_prediction", 1, 0)),
        "rf_false_positives": len(error_subset("rf_prediction", 0, 1)),
        "rf_false_negatives": len(error_subset("rf_prediction", 1, 0)),
    }
    print()
    print("=" * 100)
    print("FALSE POSITIVE / FALSE NEGATIVE COUNTS (threshold=0.5 predictions)")
    print("=" * 100)
    for key, value in error_summary.items():
        print(f"  {key}: {value}")

    error_df.to_csv(ARTIFACT_DIR / "test_set_predictions_and_errors.csv", index=False)
    print(f"Full per-claim test-set predictions/errors saved to {ARTIFACT_DIR / 'test_set_predictions_and_errors.csv'}")

    # ---- SHAP explainability examples: top-5 highest-RF-risk test claims ----
    top5_idx = np.argsort(-rf_proba)[:5]
    X_explain = X_test.iloc[top5_idx]
    claim_ids_explain = df.iloc[test_idx]["Claim_ID"].values[top5_idx]

    explanations = []
    for model_kind, pipeline, proba_all in [("logistic_regression", lr_pipeline, lr_proba), ("random_forest", rf_pipeline, rf_proba)]:
        _, _, top_factors_per_row = explain_claims(pipeline, model_kind, X_train, X_explain, top_n=3)
        for row_i, claim_id in enumerate(claim_ids_explain):
            reason_codes = to_reason_codes(top_factors_per_row[row_i])
            probability = float(proba_all[top5_idx[row_i]])
            explanation = build_claim_explanation(str(claim_id), risk_level_from_probability(probability), reason_codes)
            explanation["model"] = model_kind
            explanation["probability"] = probability
            explanation["top_shap_features"] = top_factors_per_row[row_i]
            explanations.append(explanation)

    with open(ARTIFACT_DIR / "shap_example_explanations.json", "w") as f:
        json.dump(explanations, f, indent=2, default=str)
    print()
    print("=" * 100)
    print("SHAP EXPLAINABILITY - example claim-level explanations")
    print("=" * 100)
    for explanation in explanations:
        print(f"  Claim {explanation['claim_id']} ({explanation['model']}, p={explanation['probability']:.3f}): "
              f"{explanation['fraud_screening_risk']} risk - {[f['code'] for f in explanation['contributing_factors']]}")
    print(f"Full explanation examples saved to {ARTIFACT_DIR / 'shap_example_explanations.json'}")

    # ---- Save model artifacts ----
    joblib.dump(lr_pipeline, ARTIFACT_DIR / "logistic_regression_fraud_label.pkl")
    joblib.dump(rf_pipeline, ARTIFACT_DIR / "random_forest_fraud_label.pkl")
    with open(ARTIFACT_DIR / "rule_baseline_calibration.json", "w") as f:
        json.dump(rule_calibration, f, indent=2, default=str)
    with open(ARTIFACT_DIR / "evaluation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Test claims: {len(test_idx)}  |  Customer overlap: 0  |  Target: {TARGET} (synthetic proxy label - see AI_ML_DATASET_AUDIT.md)")
    best_pr_auc = max(
        ((name, m["pr_auc"]) for name, m in results.items() if m["pr_auc"] is not None),
        key=lambda item: item[1],
    )
    print(f"Highest PR-AUC (the recommended comparison metric given the class imbalance): {best_pr_auc[0]} = {best_pr_auc[1]:.3f}")
    print("This is a synthetic-data validation study only - see docs/project_documentation/AI_VS_NON_AI_RESULTS.md")


if __name__ == "__main__":
    main()
