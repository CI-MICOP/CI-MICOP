"""Transparent uncertainty estimation (Part D).

`confidence_score` is NOT a calibrated probability - it is a documented
combination of:
  1. coverage    - fraction of the 7 defined signals that were AVAILABLE
  2. agreement   - how much the available signals agree with each other
                   (1 - population std-dev of their [0,1] values)
  3. signal trust - the mean per-signal `confidence` (e.g. the fraud-
                   screening signal is fixed low per its Step 5.2/5.3
                   near-chance finding - see signal_builder.py)
  4. model reliability - a fixed, documented discount applied whenever
                   any model/rule-screening-derived signal contributes,
                   independent of that signal's own `confidence`, to make
                   the "the underlying predictive model is near chance
                   level" finding structurally impossible to miss

`confidence_score` and `overall_risk_score` are deliberately independent
axes - see `ai_ml.risk_fusion.fusion_engine` for the risk score. A claim
can be HIGH risk + LOW confidence (e.g. one strong-but-unreliable signal
fired, nothing else corroborates it) or LOW risk + LOW confidence (too
little evidence to say anything) - this module never collapses that
distinction.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import numpy as np

from ai_ml.risk_fusion.signal_schema import Signal, SignalAvailability

TOTAL_DEFINED_SIGNALS = 7

# Fixed, documented discount applied whenever a model/rule-screening
# signal (currently only fraud_screening_rule_score) contributes -
# independent of its own per-signal confidence - reflecting Step 5.2/5.3's
# repeated-CV finding that the underlying predictive approach performs
# only marginally above chance. Not derived per-claim; a deliberate,
# constant, research-honesty adjustment.
MODEL_RELIABILITY_DISCOUNT = 0.85
MODEL_DERIVED_SIGNAL_NAMES = {"fraud_screening_rule_score"}

DEFAULT_CONFIDENCE_BAND_THRESHOLDS = {"HIGH_CONFIDENCE": 0.70, "MEDIUM_CONFIDENCE": 0.45, "LOW_CONFIDENCE": 0.25}
MIN_SIGNALS_FOR_ANY_CONFIDENCE = 2


def calibrate_confidence_band_thresholds(reference_confidence_scores: list[float]) -> dict[str, float]:
    """Percentile-based band thresholds computed from a reference
    population's OWN confidence-score distribution.

    `confidence_score` has no ground-truth label to calibrate against
    (unlike Fraud_Label/Risk_Category etc.) - it is an internal
    data-quality/agreement metric, so using its own empirical
    distribution to set readable band boundaries is unsupervised
    normalization, not label-based tuning. On CI-MICOP's current
    654-claim dataset every claim happens to have all 7 signals
    available, which compresses `confidence_score` into a narrow range
    around ~0.55 (documented in RISK_FUSION_AND_UNCERTAINTY.md) - the
    fixed `DEFAULT_CONFIDENCE_BAND_THRESHOLDS` would then place nearly
    every claim in MEDIUM_CONFIDENCE. Falls back to the fixed defaults
    when fewer than 10 reference scores are available (too few
    percentiles to be meaningful)."""
    if len(reference_confidence_scores) < 10:
        return dict(DEFAULT_CONFIDENCE_BAND_THRESHOLDS)
    scores = [s for s in reference_confidence_scores if s is not None]
    return {
        "HIGH_CONFIDENCE": float(np.percentile(scores, 85)),
        "MEDIUM_CONFIDENCE": float(np.percentile(scores, 50)),
        "LOW_CONFIDENCE": float(np.percentile(scores, 15)),
    }


@dataclass
class UncertaintyResult:
    claim_id: str
    confidence_score: float
    uncertainty_score: float
    confidence_band: str
    uncertainty_reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "confidence_score": self.confidence_score,
            "uncertainty_score": self.uncertainty_score,
            "confidence_band": self.confidence_band,
            "uncertainty_reasons": self.uncertainty_reasons,
        }


def _confidence_band(confidence: float, n_available: int, thresholds: dict[str, float]) -> str:
    if n_available < MIN_SIGNALS_FOR_ANY_CONFIDENCE:
        return "INSUFFICIENT_EVIDENCE"
    if confidence >= thresholds["HIGH_CONFIDENCE"]:
        return "HIGH_CONFIDENCE"
    if confidence >= thresholds["MEDIUM_CONFIDENCE"]:
        return "MEDIUM_CONFIDENCE"
    if confidence >= thresholds["LOW_CONFIDENCE"]:
        return "LOW_CONFIDENCE"
    # Below the lowest confidence threshold. Only escalate to
    # INSUFFICIENT_EVIDENCE if a signal is genuinely missing for this
    # claim - a fully-evidenced claim whose signals simply disagree
    # strongly is LOW_CONFIDENCE, not "insufficient evidence": all the
    # evidence that could exist for it does exist, it just disagrees.
    # Mislabeling that as "insufficient evidence" would misrepresent
    # what data is actually available for the claim.
    if n_available < TOTAL_DEFINED_SIGNALS:
        return "INSUFFICIENT_EVIDENCE"
    return "LOW_CONFIDENCE"


def compute_uncertainty(claim_id: str, signals: list[Signal], band_thresholds: dict[str, float] | None = None) -> UncertaintyResult:
    available = [s for s in signals if s.availability == SignalAvailability.AVAILABLE and s.signal_value is not None]
    reasons: list[str] = []

    coverage = len(available) / TOTAL_DEFINED_SIGNALS
    if len(available) < TOTAL_DEFINED_SIGNALS:
        missing = [s.signal_name for s in signals if s not in available]
        reasons.append(f"Only {len(available)}/{TOTAL_DEFINED_SIGNALS} signals available (missing: {', '.join(missing)}).")

    if len(available) < MIN_SIGNALS_FOR_ANY_CONFIDENCE:
        reasons.append("Fewer than 2 signals available - insufficient evidence to assess this claim reliably.")
        return UncertaintyResult(claim_id, 0.0, 1.0, "INSUFFICIENT_EVIDENCE", reasons)

    values = [s.signal_value for s in available]
    agreement = 1.0 - (statistics.pstdev(values) if len(values) > 1 else 0.0)
    agreement = max(0.0, min(1.0, agreement))
    if agreement < 0.6:
        reasons.append(f"Available signals disagree with each other (agreement={agreement:.2f}) - some indicate risk, others do not.")

    signal_trust = sum(s.confidence for s in available) / len(available)

    model_derived_present = any(s.signal_name in MODEL_DERIVED_SIGNAL_NAMES for s in available)
    reliability_multiplier = MODEL_RELIABILITY_DISCOUNT if model_derived_present else 1.0
    if model_derived_present:
        reasons.append(
            "Includes a model/rule-screening-derived signal (fraud_screening_rule_score) which Step 5.2/5.3 "
            "found performs only marginally above chance under repeated grouped cross-validation - confidence "
            "is discounted accordingly."
        )

    confidence = coverage * agreement * signal_trust * reliability_multiplier
    confidence = float(max(0.0, min(1.0, confidence)))
    uncertainty = 1.0 - confidence
    band = _confidence_band(confidence, len(available), band_thresholds or DEFAULT_CONFIDENCE_BAND_THRESHOLDS)

    if not reasons:
        reasons.append("All signals available and in agreement; no specific uncertainty driver identified.")

    return UncertaintyResult(claim_id, confidence, uncertainty, band, reasons)
