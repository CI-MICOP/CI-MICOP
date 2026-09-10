"""Tests for the Step 5.3 secondary-target validation pipeline. Run with:
    pytest ai_ml/tests/test_secondary_targets.py -v

Reuses the real (read-only) dataset via the same claim-level dataset
fixture pattern as test_fraud_pipeline.py, so these also double as a
regression check against docs/project_documentation/AI_ML_DATASET_AUDIT.md
and SECONDARY_TARGET_RESULTS.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_ml.common.feature_builder import build_claim_level_dataset
from ai_ml.models.train_fraud_models import add_engineered_features, classify_feature_columns
from ai_ml.secondary_targets.cv_runner import run_binary_cv, run_multiclass_cv, run_rule_baseline_cv
from ai_ml.secondary_targets.rule_baselines import ExcessiveAmountRuleScreener, calibrate_rule_baseline_v2
from ai_ml.secondary_targets.target_audit import (
    SECONDARY_TARGETS,
    audit_target,
    leakage_report,
    secondary_safe_feature_columns,
)
from ai_ml.secondary_targets.validation import choose_fold_count, make_folds, summarize_stability


@pytest.fixture(scope="module")
def claim_df() -> pd.DataFrame:
    return add_engineered_features(build_claim_level_dataset())


# ---------------------------------------------------------------- grain / secondary target validation


def test_one_row_per_claim(claim_df):
    assert len(claim_df) == 654
    assert claim_df["Claim_ID"].is_unique


@pytest.mark.parametrize("target", SECONDARY_TARGETS)
def test_secondary_target_audit(claim_df, target):
    audit = audit_target(target, claim_df)
    assert audit["exists"]
    assert audit["missing_values"] == 0
    assert audit["claim_id_unique"]
    assert audit["n_classes"] == len(audit["class_counts"])
    assert sum(audit["class_counts"].values()) == len(claim_df)
    assert audit["min_class_size"] >= 1


def test_excessive_amount_target_is_binary(claim_df):
    audit = audit_target("est_Excessive_Claim_Amount_Indicator", claim_df)
    assert audit["n_classes"] == 2


def test_risk_category_and_consistency_status_are_multiclass(claim_df):
    assert audit_target("frd_Risk_Category", claim_df)["n_classes"] == 4
    assert audit_target("cdc_Overall_Consistency_Status", claim_df)["n_classes"] == 3


# ---------------------------------------------------------------- target-specific leakage exclusion


@pytest.mark.parametrize("target", SECONDARY_TARGETS)
def test_leakage_report_categories_are_disjoint(claim_df, target):
    report = leakage_report(target, claim_df)
    safe, potential, definite = set(report["safe_features"]), set(report["potential_leakage"]), set(report["definite_leakage"])
    assert safe & potential == set()
    assert safe & definite == set()
    assert potential & definite == set()
    assert target in definite, "the target column itself must always be classified as definite leakage"
    assert target not in safe


def test_risk_category_excludes_fraud_label_as_definite_leakage(claim_df):
    report = leakage_report("frd_Risk_Category", claim_df)
    assert "frd_Fraud_Label" in report["definite_leakage"]
    assert "frd_Fraud_Label" not in report["safe_features"]


def test_excessive_amount_excludes_cross_table_duplicate(claim_df):
    report = leakage_report("est_Excessive_Claim_Amount_Indicator", claim_df)
    assert "frd_Excessive_Claim_Amount_Indicator" in report["definite_leakage"]
    assert "frd_Excessive_Claim_Amount_Indicator" not in report["safe_features"]


def test_excessive_amount_restores_legitimate_estimate_fields(claim_df):
    safe_cols = secondary_safe_feature_columns("est_Excessive_Claim_Amount_Indicator", claim_df)
    for restored in ["est_Repair_Estimate", "est_Repair_Cost", "est_Estimated_Repair_Days"]:
        assert restored in safe_cols


def test_consistency_status_excludes_its_own_table_as_potential_leakage(claim_df):
    report = leakage_report("cdc_Overall_Consistency_Status", claim_df)
    assert any(c.startswith("cdc_") for c in report["potential_leakage"])
    assert all(not c.startswith("cdc_") for c in report["safe_features"])


# ---------------------------------------------------------------- grouped validation / no overlap


def test_choose_fold_count_reduces_or_skips_for_small_classes():
    assert choose_fold_count(min_class_size=200) == 5
    assert choose_fold_count(min_class_size=4) == 4
    assert choose_fold_count(min_class_size=2) == 0  # below MIN_FOLDS -> skip, never force degenerate folds


def test_make_folds_has_zero_customer_overlap(claim_df):
    folds = make_folds(claim_df, "est_Excessive_Claim_Amount_Indicator", n_splits=5, random_state=42)
    assert len(folds) == 5
    for train_idx, val_idx in folds:
        train_customers = set(claim_df.iloc[train_idx]["Customer_ID"])
        val_customers = set(claim_df.iloc[val_idx]["Customer_ID"])
        assert train_customers & val_customers == set()
        assert len(train_idx) + len(val_idx) == len(claim_df)


def test_make_folds_multiclass_has_zero_customer_overlap(claim_df):
    folds = make_folds(claim_df, "frd_Risk_Category", n_splits=5, random_state=42)
    for train_idx, val_idx in folds:
        train_customers = set(claim_df.iloc[train_idx]["Customer_ID"])
        val_customers = set(claim_df.iloc[val_idx]["Customer_ID"])
        assert train_customers & val_customers == set()


# ---------------------------------------------------------------- preprocessing (binary + multiclass)


def test_binary_preprocessing_excludes_identifiers(claim_df):
    safe_cols = secondary_safe_feature_columns("est_Excessive_Claim_Amount_Indicator", claim_df)
    report = classify_feature_columns(claim_df, safe_cols)
    used = set(report["numeric"]) | set(report["categorical"])
    assert "cust_Customer_Name" not in used
    assert "Claim_Description" not in used


def test_multiclass_preprocessing_excludes_identifiers(claim_df):
    safe_cols = secondary_safe_feature_columns("frd_Risk_Category", claim_df)
    report = classify_feature_columns(claim_df, safe_cols)
    used = set(report["numeric"]) | set(report["categorical"])
    assert "cust_Phone" not in used
    assert "veh_Registration_Number" not in used


# ---------------------------------------------------------------- CV runners (small smoke tests)


def test_run_binary_cv_produces_expected_shape(claim_df):
    safe_cols = secondary_safe_feature_columns("est_Excessive_Claim_Amount_Indicator", claim_df)
    cv_df, meta = run_binary_cv(
        claim_df, "est_Excessive_Claim_Amount_Indicator", safe_cols,
        model_names=("logistic_regression",), max_folds=3, seeds=[42],
    )
    assert not meta["skipped"]
    assert len(cv_df) == meta["n_splits"] * meta["n_repeats"]
    assert set(cv_df["model"].unique()) == {"logistic_regression"}
    assert cv_df["accuracy"].between(0, 1).all()


def test_run_multiclass_cv_produces_expected_shape(claim_df):
    safe_cols = secondary_safe_feature_columns("cdc_Overall_Consistency_Status", claim_df)
    cv_df, meta = run_multiclass_cv(
        claim_df, "cdc_Overall_Consistency_Status", safe_cols,
        model_names=("logistic_regression",), max_folds=3, seeds=[42],
    )
    assert not meta["skipped"]
    assert meta["n_classes"] == 3
    assert cv_df["macro_f1"].between(0, 1).all()


def test_run_rule_baseline_cv_for_excessive_amount(claim_df):
    cv_df, meta = run_rule_baseline_cv(
        claim_df, "est_Excessive_Claim_Amount_Indicator",
        lambda: ExcessiveAmountRuleScreener(), "rule_baseline", max_folds=3, seeds=[42],
    )
    assert not meta["skipped"]
    assert cv_df["precision"].between(0, 1).all()


# ---------------------------------------------------------------- metric / stability calculation


def test_summarize_stability_known_values():
    stats = summarize_stability([0.2, 0.4, 0.3, 0.5, 0.1])
    assert stats["n"] == 5
    assert stats["mean"] == pytest.approx(0.3)
    assert stats["min"] == 0.1
    assert stats["max"] == 0.5
    assert stats["ci95"][0] < stats["mean"] < stats["ci95"][1]


def test_summarize_stability_handles_empty_and_single_value():
    empty_stats = summarize_stability([])
    assert empty_stats["n"] == 0
    assert empty_stats["ci95"] is None

    single_stats = summarize_stability([0.42])
    assert single_stats["n"] == 1
    assert single_stats["mean"] == 0.42
    assert single_stats["ci95"] is None


def test_summarize_stability_ignores_none_values():
    stats = summarize_stability([0.5, None, 0.7, None])
    assert stats["n"] == 2


# ---------------------------------------------------------------- rule baseline v2


def test_calibrate_rule_baseline_v2_picks_a_candidate_threshold(claim_df):
    from ai_ml.experiments.run_fraud_experiment import create_grouped_split

    train_idx, _ = create_grouped_split(claim_df)
    train_df = claim_df.iloc[train_idx]
    screener, calibration = calibrate_rule_baseline_v2(train_df, candidate_thresholds=(0.5, 1.0, 1.5, 2.0))
    assert calibration["chosen_overall_threshold"] in (0.5, 1.0, 1.5, 2.0)
    assert screener._fitted
    predictions = screener.predict(train_df)
    assert set(predictions["Rule_Baseline_Prediction"].unique()).issubset({0, 1})


def test_excessive_amount_rule_screener_requires_fit(claim_df):
    screener = ExcessiveAmountRuleScreener()
    with pytest.raises(RuntimeError):
        screener.predict(claim_df)
