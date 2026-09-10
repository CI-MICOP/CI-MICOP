"""Tests for the Step 5.2 fraud-experiment pipeline. Run with:
    pytest ai_ml/tests/test_fraud_pipeline.py -v
(or as part of the full suite; see the repo's other test directories).

These tests exercise the REAL dataset (read-only) rather than a mock, so
they double as a regression check that the dataset/pipeline still agree
with the invariants documented in AI_ML_DATASET_AUDIT.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener
from ai_ml.common.feature_builder import (
    build_claim_level_dataset,
    leaked_columns_for_target,
    safe_feature_columns,
)
from ai_ml.experiments.run_fraud_experiment import TARGET, create_grouped_split, load_and_validate
from ai_ml.explainability.reason_codes import build_claim_explanation, reason_code_for_feature
from ai_ml.models.evaluation import evaluate_binary
from ai_ml.models.train_fraud_models import (
    add_engineered_features,
    build_preprocessor,
    classify_feature_columns,
    train_logistic_regression,
)


@pytest.fixture(scope="module")
def claim_df() -> pd.DataFrame:
    return add_engineered_features(build_claim_level_dataset())


# ---------------------------------------------------------------- grain


def test_one_row_per_claim(claim_df):
    assert len(claim_df) == 654
    assert claim_df["Claim_ID"].is_unique


# ---------------------------------------------------------------- target validation


def test_target_exists_and_is_binary(claim_df):
    assert TARGET in claim_df.columns
    values = set(claim_df[TARGET].dropna().unique().tolist())
    assert values.issubset({0, 1})
    assert values == {0, 1}  # both classes actually present


def test_load_and_validate_raises_on_missing_target(claim_df, monkeypatch):
    def fake_builder():
        return claim_df.drop(columns=[TARGET])

    monkeypatch.setattr("ai_ml.experiments.run_fraud_experiment.build_claim_level_dataset", fake_builder)
    with pytest.raises(ValueError):
        load_and_validate()


def test_load_and_validate_raises_on_duplicate_claim_id(claim_df, monkeypatch):
    dup_df = pd.concat([claim_df, claim_df.iloc[[0]]], ignore_index=True)

    def fake_builder():
        return dup_df

    monkeypatch.setattr("ai_ml.experiments.run_fraud_experiment.build_claim_level_dataset", fake_builder)
    with pytest.raises(AssertionError):
        load_and_validate()


# ---------------------------------------------------------------- grouped split / customer leakage


def test_grouped_split_has_zero_customer_overlap(claim_df):
    train_idx, test_idx = create_grouped_split(claim_df)
    train_customers = set(claim_df.iloc[train_idx]["Customer_ID"])
    test_customers = set(claim_df.iloc[test_idx]["Customer_ID"])
    assert train_customers & test_customers == set()

    train_claims = set(claim_df.iloc[train_idx]["Claim_ID"])
    test_claims = set(claim_df.iloc[test_idx]["Claim_ID"])
    assert train_claims & test_claims == set()
    assert len(train_idx) + len(test_idx) == len(claim_df)


def test_grouped_split_is_reproducible(claim_df):
    train_idx_1, test_idx_1 = create_grouped_split(claim_df)
    train_idx_2, test_idx_2 = create_grouped_split(claim_df)
    assert list(train_idx_1) == list(train_idx_2)
    assert list(test_idx_1) == list(test_idx_2)


# ---------------------------------------------------------------- leakage exclusion


def test_fraud_label_excludes_its_own_table():
    df = build_claim_level_dataset()
    safe_cols = safe_feature_columns(TARGET, df)
    leaked = leaked_columns_for_target(TARGET, df)
    assert TARGET not in safe_cols
    assert all(not c.startswith("frd_") for c in safe_cols)
    assert all(not c.startswith("aud_") for c in safe_cols)
    assert all(not c.startswith("tp_") for c in safe_cols)
    assert any(c.startswith("frd_") for c in leaked)


def test_classify_feature_columns_excludes_identifiers_and_free_text(claim_df):
    safe_cols = safe_feature_columns(TARGET, claim_df)
    report = classify_feature_columns(claim_df, safe_cols)
    used = set(report["numeric"]) | set(report["categorical"])

    for identifier in ["Claim_Number", "cust_Customer_Name", "cust_Phone", "cust_Email", "cust_Address"]:
        assert identifier not in used, f"{identifier} is an identifier/PII column and must not be modeled"
    for free_text in ["Claim_Description", "acc_Accident_Description", "insp_Surveyor_Comments"]:
        assert free_text not in used, f"{free_text} is free text and must not be modeled"
    # No raw datetime column should ever reach scikit-learn directly.
    for col in used:
        assert not pd.api.types.is_datetime64_any_dtype(claim_df[col].dtype)


# ---------------------------------------------------------------- rule baseline


def test_rule_baseline_output_shape_and_values(claim_df):
    train_idx, test_idx = create_grouped_split(claim_df)
    screener = RuleBasedFraudScreener()
    screener.fit(claim_df.iloc[train_idx])
    predictions = screener.predict(claim_df.iloc[test_idx])

    assert list(predictions.columns) == [
        "Claim_ID", "Rule_Baseline_Prediction", "Rule_Baseline_Score", "Rule_Reason_Codes",
    ]
    assert len(predictions) == len(test_idx)
    assert set(predictions["Rule_Baseline_Prediction"].unique()).issubset({0, 1})
    assert predictions["Rule_Baseline_Score"].between(0, 1).all()


def test_rule_baseline_requires_fit_before_predict(claim_df):
    screener = RuleBasedFraudScreener()
    with pytest.raises(RuntimeError):
        screener.predict(claim_df)


# ---------------------------------------------------------------- model training (smoke test)


def test_logistic_regression_trains_and_predicts(claim_df):
    train_idx, test_idx = create_grouped_split(claim_df)
    safe_cols = safe_feature_columns(TARGET, claim_df)
    report = classify_feature_columns(claim_df, safe_cols)
    feature_cols = report["numeric"] + report["categorical"]

    X_train = claim_df.iloc[train_idx][feature_cols]
    y_train = claim_df.iloc[train_idx][TARGET].astype(int)
    X_test = claim_df.iloc[test_idx][feature_cols]

    preprocessor = build_preprocessor(report["numeric"], report["categorical"])
    pipeline = train_logistic_regression(X_train, y_train, preprocessor, class_weight="balanced")

    proba = pipeline.predict_proba(X_test)[:, 1]
    assert len(proba) == len(test_idx)
    assert np.all((proba >= 0) & (proba <= 1))


# ---------------------------------------------------------------- metrics


def test_evaluate_binary_basic_metrics():
    y_true = [0, 0, 0, 1, 1, 1, 1]
    y_pred = [0, 1, 0, 1, 1, 0, 1]
    y_score = [0.1, 0.6, 0.2, 0.8, 0.9, 0.4, 0.7]
    metrics = evaluate_binary(y_true, y_pred, y_score)

    assert metrics["n_test"] == 7
    assert metrics["roc_auc"] is not None
    assert metrics["pr_auc"] is not None
    assert 0 <= metrics["precision"] <= 1
    assert 0 <= metrics["recall"] <= 1


def test_evaluate_binary_handles_single_class_test_set():
    y_true = [0, 0, 0, 0]
    y_pred = [0, 1, 0, 0]
    metrics = evaluate_binary(y_true, y_pred, y_score=[0.1, 0.6, 0.2, 0.3])
    assert metrics["roc_auc"] is None
    assert metrics["pr_auc"] is None
    assert "note" in metrics


# ---------------------------------------------------------------- reason codes


def test_reason_code_for_feature_matches_known_prefixes():
    assert reason_code_for_feature("cdc_Document_Mismatch_Indicator") == "DOCUMENT_INCONSISTENCY"
    assert reason_code_for_feature("est_Repair_Estimate") == "REPAIR_ESTIMATE_ANOMALY"
    assert reason_code_for_feature("evidence_any_duplicate_flag") == "DUPLICATE_EVIDENCE"
    assert reason_code_for_feature("cust_Age") == "UNUSUAL_CLAIM_PATTERN"  # unmatched -> fallback


def test_build_claim_explanation_structure():
    explanation = build_claim_explanation("CLM-TEST-0001", "HIGH", ["DOCUMENT_INCONSISTENCY", "DUPLICATE_EVIDENCE"])
    assert explanation["claim_id"] == "CLM-TEST-0001"
    assert explanation["fraud_screening_risk"] == "HIGH"
    assert len(explanation["contributing_factors"]) == 2
    assert "not proof of fraud" in explanation["disclaimer"]
