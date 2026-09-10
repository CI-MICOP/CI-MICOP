"""Tests for the Step 5.7 consolidated AI-vs-non-AI evaluation. Run with:
    pytest ai_ml/tests/test_final_evaluation.py -v

These tests read the SAME real Step 5.2/5.3/5.4/5.6 artifact files the
report itself reads - they exist to catch a mismatch between the
generated comparison table and the actual prior-step results, not to
re-derive those results independently.
"""

from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from ai_ml.experiments.run_final_evaluation import (
    OUTPUT_DIR,
    STEP52_RESULTS,
    STEP53_RESULTS,
    STEP54_RESULTS,
    STEP56_RESULTS,
    build_capability_rows,
    build_final_comparison_table,
    build_quantitative_rows,
    generate_final_conclusion,
    load_source_results,
)

REQUIRED_COLUMNS = [
    "component", "baseline_method", "ai_method", "metric", "baseline_value", "ai_value",
    "difference", "statistical_significance", "interpretation", "data_source", "measured_or_qualitative",
]


@pytest.fixture(scope="module")
def sources():
    return load_source_results()


@pytest.fixture(scope="module")
def table(sources):
    return build_final_comparison_table()


# ---------------------------------------------------------------- comparison table generation


def test_table_has_required_columns(table):
    assert list(table.columns) == REQUIRED_COLUMNS


def test_table_is_non_empty_and_covers_both_row_types(table):
    assert len(table) > 0
    kinds = set(table["measured_or_qualitative"])
    assert kinds == {"quantitative", "qualitative"}


# ---------------------------------------------------------------- no fabricated numeric results


def test_quantitative_values_are_traceable_to_a_real_source_file(table):
    quantitative = table[table["measured_or_qualitative"] == "quantitative"]
    allowed_sources = {
        "Step 5.2 evaluation_results.json", "Step 5.3 secondary_targets_summary.json",
        "Step 5.4 risk_fusion_summary.json", "Step 5.6 aco_results.csv",
    }
    assert set(quantitative["data_source"]).issubset(allowed_sources)


def test_no_numeric_value_is_a_suspicious_round_number(table):
    """A quick fabrication smoke check: hand-typed "nice" numbers like
    exactly 0.9 or 100.0 would be suspicious for measured ML metrics -
    the real values all have many decimal digits of floating-point noise."""
    quantitative = table[table["measured_or_qualitative"] == "quantitative"]
    for value in quantitative["baseline_value"]:
        if isinstance(value, float) and value not in (0.0, 1.0):
            assert value != round(value, 1), f"suspiciously round value: {value}"


# ---------------------------------------------------------------- correct baseline / AI values


def test_fraud_single_split_values_match_step52_source(sources):
    step52 = sources["step52"]
    rows = build_quantitative_rows(sources)
    row = next(r for r in rows if r["component"] == "Fraud screening (single split)" and r["ai_method"] == "Logistic Regression" and r["metric"] == "PR-AUC")
    assert row["baseline_value"] == pytest.approx(step52["rule_baseline"]["pr_auc"], abs=1e-4)
    assert row["ai_value"] == pytest.approx(step52["logistic_regression_0.5"]["pr_auc"], abs=1e-4)


def test_fraud_repeated_cv_values_match_step53_source(sources):
    step53 = sources["step53"]
    rows = build_quantitative_rows(sources)
    row = next(r for r in rows if r["component"].startswith("Fraud screening (5-fold") and r["ai_method"] == "Random Forest")
    fr = step53["fraud_robustness"]["repeated_cv"]["stability_by_model"]
    assert row["ai_value"] == pytest.approx(fr["random_forest"]["pr_auc"]["mean"], abs=1e-4)


def test_surveyor_assignment_values_match_step56_source(sources):
    step56 = sources["step56"]
    rows = build_quantitative_rows(sources)
    row = next(r for r in rows if r["metric"] == "Total assignment cost")
    aco_row = step56[step56["Metric"] == "Total Cost"].iloc[0]
    assert row["baseline_value"] == pytest.approx(aco_row["Baseline (greedy)"], abs=1e-4)
    assert row["ai_value"] == pytest.approx(aco_row["ACO"], abs=1e-4)


# ---------------------------------------------------------------- difference calculation


def test_difference_equals_ai_minus_baseline_for_all_quantitative_rows(table):
    quantitative = table[table["measured_or_qualitative"] == "quantitative"]
    for _, row in quantitative.iterrows():
        expected = row["ai_value"] - row["baseline_value"]
        assert row["difference"] == pytest.approx(expected, abs=1e-3)


def test_runtime_difference_shows_aco_is_slower(table):
    row = table[(table["metric"] == "Runtime (seconds)")].iloc[0]
    assert row["difference"] > 0
    assert "slower" in row["interpretation"].lower()


# ---------------------------------------------------------------- qualitative result handling


def test_qualitative_rows_never_carry_a_numeric_difference():
    rows = build_capability_rows()
    assert len(rows) > 0
    for row in rows:
        assert row["measured_or_qualitative"] == "qualitative"
        assert row["difference"] == "N/A"
        assert row["statistical_significance"] == "N/A (qualitative)"


def test_capability_status_uses_the_approved_vocabulary():
    allowed = {"AVAILABLE", "PARTIAL", "EXPERIMENTAL", "NOT MEASURED"}
    for row in build_capability_rows():
        assert row["ai_value"] in allowed


# ---------------------------------------------------------------- final conclusion generation


def test_final_conclusion_is_nuanced_not_a_blanket_claim(table):
    conclusion = generate_final_conclusion(table)
    assert isinstance(conclusion, str) and len(conclusion) > 100
    lowered = conclusion.lower()
    assert "not universally" in lowered
    for forbidden in ["always better", "guarantees", "100% accurate", "production-ready", "first ever"]:
        assert forbidden not in lowered


# ---------------------------------------------------------------- workflow artifact existence


def test_required_source_artifacts_exist():
    for path in (STEP52_RESULTS, STEP53_RESULTS, STEP54_RESULTS, STEP56_RESULTS):
        assert path.exists(), f"missing prerequisite artifact: {path}"


def test_output_artifacts_exist_after_running_main():
    from ai_ml.experiments.run_final_evaluation import main

    main()
    assert (OUTPUT_DIR / "final_comparison.csv").exists()
    assert (OUTPUT_DIR / "ci_micop_ai_vs_non_ai.png").exists()
    assert (OUTPUT_DIR / "final_conclusion.txt").exists()

    reloaded = pd.read_csv(OUTPUT_DIR / "final_comparison.csv")
    assert list(reloaded.columns) == REQUIRED_COLUMNS


def test_missing_source_file_fails_loudly_rather_than_fabricating(tmp_path, monkeypatch):
    import ai_ml.experiments.run_final_evaluation as module

    fake_missing_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(module, "STEP52_RESULTS", fake_missing_path)
    with pytest.raises(FileNotFoundError):
        module.load_source_results()
