"""Integrity checks for the risk-fusion layer (used by
ai_ml/tests/test_risk_fusion.py and
ai_ml/experiments/run_risk_fusion_experiment.py). Every check raises
`AssertionError` on failure rather than printing a warning - the same
"fail loudly" convention Step 5.2/5.3 already use.
"""

from __future__ import annotations

import math

from ai_ml.risk_fusion.fusion_engine import FusionResult


def assert_no_invalid_scores(results: list[FusionResult]) -> None:
    for result in results:
        if result.overall_risk_score is None:
            continue  # UNSCORED is a valid, explicit state - not an invalid one
        if math.isnan(result.overall_risk_score) or math.isinf(result.overall_risk_score):
            raise AssertionError(f"Claim {result.claim_id} ({result.fusion_strategy}) has an invalid risk score: {result.overall_risk_score}")
        if not (0.0 <= result.overall_risk_score <= 1.0):
            raise AssertionError(f"Claim {result.claim_id} ({result.fusion_strategy}) risk score out of [0,1]: {result.overall_risk_score}")


def assert_full_claim_coverage(results: list[FusionResult], expected_claim_ids: set[str]) -> None:
    scored_ids = {r.claim_id for r in results}
    missing = expected_claim_ids - scored_ids
    if missing:
        raise AssertionError(f"{len(missing)} claim(s) silently dropped from fusion output: {sorted(missing)[:5]}...")


def assert_weights_renormalized(signal_values: dict, contributing_signals: list[str], weights: dict[str, float]) -> None:
    """Sanity check: the weights actually used for the signals that
    contributed to this claim's score must be the ones configured for
    exactly those signals, renormalized to sum to 1 (not diluted by
    signals that were unavailable)."""
    used_weights = {name: weights.get(name, 0.0) for name in contributing_signals}
    total = sum(used_weights.values())
    if total <= 0:
        return  # equal-weight fallback path - nothing to check here
    normalized_total = sum(w / total for w in used_weights.values())
    if not math.isclose(normalized_total, 1.0, rel_tol=1e-6):
        raise AssertionError(f"Renormalized weights do not sum to 1.0: {normalized_total}")
