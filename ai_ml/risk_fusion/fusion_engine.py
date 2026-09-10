"""Transparent, weighted-sum multi-signal fusion (Part B/C).

Deliberately NOT a trained model: `overall_risk_score` is a documented,
renormalized weighted average of whichever `Signal`s are AVAILABLE for a
claim. Two strategies are provided so they can be compared head-to-head
in `ai_ml.experiments.run_risk_fusion_experiment`:

  - `equal_weight_fusion`: every available signal counts the same.
  - `configurable_weighted_fusion`: fixed, documented, NOT learned or
    statistically optimized weights (see `CONFIGURABLE_FUSION_WEIGHTS`).
    Chosen by domain reasoning about which signal families are most
    directly tied to claim-handling risk, not by tuning against any
    test set - Step 5.2/5.3 already established that this dataset's
    labels do not reliably support that kind of tuning.

Missing signals are never treated as zero risk: they are excluded from
the weighted sum and the remaining weights are renormalized to sum to 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_ml.risk_fusion.signal_schema import Signal, SignalAvailability

# "Configurable fusion weights" - a research-prototype starting point,
# not a learned or statistically optimized weighting. Reasoning: fraud
# screening and document consistency are given the most weight as the
# two signal families most directly linked to claim-handling risk in
# the existing rule-baseline design (Step 5.2); information quality is
# weighted lowest since it speaks more to *how much to trust* the other
# signals (see uncertainty.py) than to risk itself.
CONFIGURABLE_FUSION_WEIGHTS: dict[str, float] = {
    "document_consistency_mismatch": 0.20,
    "repair_estimate_anomaly": 0.20,
    "evidence_duplication": 0.15,
    "fraud_screening_rule_score": 0.20,
    "claim_pattern_anomaly": 0.10,
    "document_completeness": 0.10,
    "information_quality": 0.05,
}

# "Prototype research thresholds" - chosen for readable workflow
# prioritization (roughly quartile-shaped bands), NOT validated against
# any clinical/actuarial/regulatory standard and NOT tuned against
# outcome labels.
RISK_BAND_THRESHOLDS = {"CRITICAL": 0.75, "HIGH": 0.50, "MEDIUM": 0.25}


@dataclass
class FusionResult:
    claim_id: str
    fusion_strategy: str
    overall_risk_score: float | None
    risk_band: str
    contributing_signals: list[str]
    unavailable_signals: list[str]
    evidence_count: int
    signal_values: dict[str, float | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "fusion_strategy": self.fusion_strategy,
            "overall_risk_score": self.overall_risk_score,
            "risk_band": self.risk_band,
            "risk_band_label": "Prototype research risk band - workflow prioritization only, not a validated insurance risk threshold.",
            "contributing_signals": self.contributing_signals,
            "unavailable_signals": self.unavailable_signals,
            "evidence_count": self.evidence_count,
            "signal_values": self.signal_values,
        }


def risk_band_from_score(score: float | None) -> str:
    if score is None:
        return "UNSCORED"
    if score >= RISK_BAND_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= RISK_BAND_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= RISK_BAND_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _fuse(claim_id: str, signals: list[Signal], weights: dict[str, float], strategy_name: str) -> FusionResult:
    available = [s for s in signals if s.availability == SignalAvailability.AVAILABLE and s.signal_value is not None]
    unavailable = [s.signal_name for s in signals if s not in available]

    signal_values = {s.signal_name: s.signal_value for s in signals}

    if not available:
        return FusionResult(
            claim_id=claim_id, fusion_strategy=strategy_name, overall_risk_score=None, risk_band="UNSCORED",
            contributing_signals=[], unavailable_signals=unavailable, evidence_count=0, signal_values=signal_values,
        )

    raw_weights = {s.signal_name: weights.get(s.signal_name, 0.0) for s in available}
    weight_total = sum(raw_weights.values())
    if weight_total <= 0:
        # Every available signal happened to have zero configured weight
        # (should not occur with the current signal set, but never
        # silently divide by zero) - fall back to equal weighting among
        # the available signals rather than producing a NaN score.
        normalized_weights = {name: 1.0 / len(available) for name in raw_weights}
    else:
        normalized_weights = {name: w / weight_total for name, w in raw_weights.items()}

    score = sum(normalized_weights[s.signal_name] * s.signal_value for s in available)
    score = float(min(max(score, 0.0), 1.0))

    return FusionResult(
        claim_id=claim_id, fusion_strategy=strategy_name, overall_risk_score=score, risk_band=risk_band_from_score(score),
        contributing_signals=[s.signal_name for s in available], unavailable_signals=unavailable,
        evidence_count=len(available), signal_values=signal_values,
    )


def equal_weight_fusion(claim_id: str, signals: list[Signal]) -> FusionResult:
    equal_weights = {s.signal_name: 1.0 for s in signals}
    return _fuse(claim_id, signals, equal_weights, "equal_weight_fusion")


def configurable_weighted_fusion(claim_id: str, signals: list[Signal], weights: dict[str, float] | None = None) -> FusionResult:
    return _fuse(claim_id, signals, weights or CONFIGURABLE_FUSION_WEIGHTS, "configurable_weighted_fusion")
