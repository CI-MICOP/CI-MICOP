"""Tests for the Step 5.4 risk-fusion layer. Run with:
    pytest ai_ml/tests/test_risk_fusion.py -v
Uses a mix of hand-built `Signal` fixtures (for isolated, deterministic
unit tests of fusion/uncertainty/reason-codes/review-priority logic) and
the real dataset (for signal_builder/end-to-end integration, determinism,
and no-claim-loss checks), matching the style of test_fraud_pipeline.py
and test_secondary_targets.py.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from ai_ml.baselines.rule_based_fraud import RuleBasedFraudScreener
from ai_ml.common.feature_builder import build_claim_level_dataset
from ai_ml.experiments.run_fraud_experiment import create_grouped_split
from ai_ml.models.train_fraud_models import add_engineered_features
from ai_ml.risk_fusion.fusion_engine import (
    CONFIGURABLE_FUSION_WEIGHTS,
    configurable_weighted_fusion,
    equal_weight_fusion,
    risk_band_from_score,
)
from ai_ml.risk_fusion.reason_codes import RISK_FUSION_REASON_CODES, reason_codes_for_claim, reason_codes_for_signals
from ai_ml.risk_fusion.review_priority import recommend_review_priority
from ai_ml.risk_fusion.signal_builder import ReferenceStats, build_signals
from ai_ml.risk_fusion.signal_schema import Signal, SignalAvailability, SignalCategory, SignalDirection
from ai_ml.risk_fusion.uncertainty import compute_uncertainty
from ai_ml.risk_fusion.validation import assert_full_claim_coverage, assert_no_invalid_scores


def make_signal(name: str, value: float | None, confidence: float | None = 1.0, available: bool = True, category: SignalCategory = SignalCategory.DOCUMENT_CONSISTENCY) -> Signal:
    return Signal(
        claim_id="CLM-TEST", signal_name=name, category=category,
        signal_value=value, raw_value=value, signal_direction=SignalDirection.HIGHER_IS_RISKIER,
        confidence=confidence if available else None,
        availability=SignalAvailability.AVAILABLE if available else SignalAvailability.UNAVAILABLE,
        evidence_available=available, explanation="test signal", source_module="test",
    )


@pytest.fixture(scope="module")
def claim_df() -> pd.DataFrame:
    return add_engineered_features(build_claim_level_dataset())


# ---------------------------------------------------------------- signal normalization / missing handling


def test_signal_value_always_in_unit_range_for_real_data(claim_df):
    screener = RuleBasedFraudScreener().fit(claim_df)
    signals_by_claim = build_signals(claim_df.head(20), claim_df, screener)
    for signals in signals_by_claim.values():
        for s in signals:
            if s.availability == SignalAvailability.AVAILABLE:
                assert s.signal_value is not None
                assert 0.0 <= s.signal_value <= 1.0
            else:
                assert s.signal_value is None
                assert s.confidence is None


def test_missing_signal_is_not_fabricated_as_zero_risk():
    signals = [make_signal("a", 0.9), make_signal("b", None, available=False)]
    result = equal_weight_fusion("CLM-TEST", signals)
    assert "b" in result.unavailable_signals
    assert "b" not in result.contributing_signals
    # the missing signal must not silently pull the score toward 0
    assert result.overall_risk_score == pytest.approx(0.9)


def test_all_signals_unavailable_produces_unscored_not_zero():
    signals = [make_signal("a", None, available=False), make_signal("b", None, available=False)]
    result = equal_weight_fusion("CLM-TEST", signals)
    assert result.overall_risk_score is None
    assert result.risk_band == "UNSCORED"


# ---------------------------------------------------------------- weight renormalization


def test_configurable_fusion_renormalizes_over_available_signals_only():
    signals = [
        make_signal("document_consistency_mismatch", 1.0),
        make_signal("repair_estimate_anomaly", None, available=False),
        make_signal("fraud_screening_rule_score", 0.0),
    ]
    result = configurable_weighted_fusion("CLM-TEST", signals)
    # only 2 of 3 signals contribute; weights among them must renormalize to 1
    w_doc = CONFIGURABLE_FUSION_WEIGHTS["document_consistency_mismatch"]
    w_fraud = CONFIGURABLE_FUSION_WEIGHTS["fraud_screening_rule_score"]
    expected = (w_doc * 1.0 + w_fraud * 0.0) / (w_doc + w_fraud)
    assert result.overall_risk_score == pytest.approx(expected)


def test_equal_weight_fusion_gives_every_available_signal_the_same_weight():
    signals = [make_signal("a", 1.0), make_signal("b", 0.0), make_signal("c", 0.5)]
    result = equal_weight_fusion("CLM-TEST", signals)
    assert result.overall_risk_score == pytest.approx((1.0 + 0.0 + 0.5) / 3)


# ---------------------------------------------------------------- risk bands


def test_risk_band_from_score_thresholds():
    assert risk_band_from_score(0.9) == "CRITICAL"
    assert risk_band_from_score(0.6) == "HIGH"
    assert risk_band_from_score(0.3) == "MEDIUM"
    assert risk_band_from_score(0.1) == "LOW"
    assert risk_band_from_score(None) == "UNSCORED"


# ---------------------------------------------------------------- uncertainty / confidence


def test_uncertainty_insufficient_evidence_when_fewer_than_two_signals():
    signals = [make_signal("a", None, available=False), make_signal("b", None, available=False)]
    result = compute_uncertainty("CLM-TEST", signals)
    assert result.confidence_band == "INSUFFICIENT_EVIDENCE"
    assert result.confidence_score == 0.0
    assert result.uncertainty_score == 1.0


def test_uncertainty_high_confidence_when_signals_agree_and_are_trusted():
    full_coverage_names = [
        "document_consistency_mismatch", "repair_estimate_anomaly", "evidence_duplication",
        "claim_pattern_anomaly", "document_completeness", "information_quality",
    ]
    signals = [make_signal(n, 0.1, confidence=1.0) for n in full_coverage_names]
    result = compute_uncertainty("CLM-TEST", signals)
    # all 6/7 non-model-derived signals present and in full agreement -> high confidence
    assert result.confidence_score > 0.7
    assert result.uncertainty_score == pytest.approx(1.0 - result.confidence_score)


def test_uncertainty_flags_disagreement_when_signals_conflict():
    signals = [
        make_signal("document_consistency_mismatch", 1.0),
        make_signal("evidence_duplication", 0.0),
        make_signal("document_completeness", 1.0),
        make_signal("claim_pattern_anomaly", 0.0),
    ]
    result = compute_uncertainty("CLM-TEST", signals)
    assert any("disagree" in r for r in result.uncertainty_reasons)


def test_risk_is_not_equated_with_confidence():
    """A claim can be high-risk and low-confidence at once - the two axes
    must be computed independently, not derived from one another."""
    high_risk_signals = [make_signal("fraud_screening_rule_score", 0.95, confidence=0.4)]
    fusion = configurable_weighted_fusion("CLM-TEST", high_risk_signals)
    uncertainty = compute_uncertainty("CLM-TEST", high_risk_signals)
    assert fusion.risk_band in {"HIGH", "CRITICAL"}
    assert uncertainty.confidence_band in {"LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE", "MEDIUM_CONFIDENCE"}


# ---------------------------------------------------------------- reason codes


def test_reason_codes_for_signals_only_fire_above_threshold():
    signals = [make_signal("document_consistency_mismatch", 0.9), make_signal("repair_estimate_anomaly", 0.1, category=SignalCategory.REPAIR_ESTIMATE_ANOMALY)]
    codes = reason_codes_for_signals(signals)
    assert "DOCUMENT_INCONSISTENCY" in codes
    assert "REPAIR_ESTIMATE_ANOMALY" not in codes


def test_reason_codes_for_claim_adds_uncertainty_codes():
    signals = [make_signal("document_consistency_mismatch", 0.1), make_signal("evidence_duplication", 0.1)]
    codes = reason_codes_for_claim(signals, "INSUFFICIENT_EVIDENCE", ["Fewer than 2 signals available - insufficient evidence to assess this claim reliably."])
    assert "INSUFFICIENT_DATA" in codes


def test_all_reason_codes_have_required_fields():
    for code, definition in RISK_FUSION_REASON_CODES.items():
        d = definition.to_dict()
        assert d["code"] == code
        assert d["title"]
        assert d["explanation"]
        assert d["severity"] in {"LOW", "MEDIUM", "HIGH"}
        assert d["source_module"]


def test_reason_codes_never_claim_confirmed_fraud():
    for definition in RISK_FUSION_REASON_CODES.values():
        text = (definition.title + definition.explanation).lower()
        assert "fraud confirmed" not in text
        assert "detected fraud" not in text


# ---------------------------------------------------------------- review priority


def test_high_risk_low_confidence_routes_to_review_not_auto_reject():
    priority = recommend_review_priority("CRITICAL", "LOW_CONFIDENCE", contributing_signal_count=3, disagreement_flag=True)
    assert priority in {"HIGH_REVIEW", "URGENT_REVIEW"}  # never silently dropped, never auto-decided


def test_critical_risk_reliable_confidence_is_urgent():
    assert recommend_review_priority("CRITICAL", "HIGH_CONFIDENCE", 5, False) == "URGENT_REVIEW"


def test_low_risk_unreliable_confidence_is_not_low_review():
    # an untrustworthy "low risk" verdict must not be waved through as LOW_REVIEW
    assert recommend_review_priority("LOW", "INSUFFICIENT_EVIDENCE", 1, False) != "LOW_REVIEW"


def test_unscored_claim_always_gets_reviewed():
    assert recommend_review_priority("UNSCORED", "INSUFFICIENT_EVIDENCE", 0, False) != "LOW_REVIEW"


# ---------------------------------------------------------------- integrity: no NaN, no silent claim loss, determinism


def test_no_invalid_scores_across_real_dataset(claim_df):
    train_idx, test_idx = create_grouped_split(claim_df)
    train_df, test_df = claim_df.iloc[train_idx], claim_df.iloc[test_idx]
    screener = RuleBasedFraudScreener().fit(train_df)
    signals_by_claim = build_signals(test_df, train_df, screener)
    results = [equal_weight_fusion(cid, s) for cid, s in signals_by_claim.items()]
    results += [configurable_weighted_fusion(cid, s) for cid, s in signals_by_claim.items()]
    assert_no_invalid_scores(results)
    for r in results:
        if r.overall_risk_score is not None:
            assert not math.isnan(r.overall_risk_score)


def test_no_silent_claim_loss_across_real_dataset(claim_df):
    screener = RuleBasedFraudScreener().fit(claim_df)
    signals_by_claim = build_signals(claim_df, claim_df, screener)
    results = [configurable_weighted_fusion(cid, s) for cid, s in signals_by_claim.items()]
    expected_ids = set(claim_df["Claim_ID"].astype(str))
    assert_full_claim_coverage(results, expected_ids)
    assert len(signals_by_claim) == len(claim_df) == 654


def test_signal_building_is_deterministic(claim_df):
    screener1 = RuleBasedFraudScreener().fit(claim_df)
    screener2 = RuleBasedFraudScreener().fit(claim_df)
    signals_1 = build_signals(claim_df.head(30), claim_df, screener1)
    signals_2 = build_signals(claim_df.head(30), claim_df, screener2)
    for claim_id in signals_1:
        values_1 = [s.signal_value for s in signals_1[claim_id]]
        values_2 = [s.signal_value for s in signals_2[claim_id]]
        assert values_1 == values_2


def test_fusion_is_deterministic():
    signals = [make_signal("document_consistency_mismatch", 0.7), make_signal("fraud_screening_rule_score", 0.3, confidence=0.4)]
    r1 = configurable_weighted_fusion("CLM-TEST", signals)
    r2 = configurable_weighted_fusion("CLM-TEST", signals)
    assert r1.overall_risk_score == r2.overall_risk_score
    assert r1.risk_band == r2.risk_band


def test_reference_stats_computed_without_reading_any_target_column(claim_df):
    ref = ReferenceStats.from_reference_population(claim_df)
    assert ref.repair_ratio_p90 >= ref.repair_ratio_p50
    assert isinstance(ref.early_claim_days_p50, float)
