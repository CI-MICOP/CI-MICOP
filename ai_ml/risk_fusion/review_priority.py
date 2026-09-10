"""Prototype research review-prioritization mechanism (Part F).

This module NEVER approves or rejects a claim. It only recommends an
ORDER in which a Claims Officer should look at claims - the officer
still makes every decision. A high-risk-but-low-confidence claim is
routed to review (never auto-rejected), because low confidence means
"we cannot tell you reliably whether this is actually risky", which is
exactly the situation a human should look at, not resolve automatically.
"""

from __future__ import annotations

REVIEW_PRIORITIES = ["URGENT_REVIEW", "HIGH_REVIEW", "STANDARD_REVIEW", "LOW_REVIEW"]

UNRELIABLE_CONFIDENCE_BANDS = {"LOW_CONFIDENCE", "INSUFFICIENT_EVIDENCE"}


def recommend_review_priority(risk_band: str, confidence_band: str, contributing_signal_count: int, disagreement_flag: bool) -> str:
    """Prototype research prioritization - NOT a decision. See module
    docstring. `disagreement_flag` should come from
    `ai_ml.risk_fusion.uncertainty` (agreement < 0.6)."""

    if risk_band == "UNSCORED" or contributing_signal_count == 0:
        return "HIGH_REVIEW"  # cannot be scored at all -> needs a human, not silently skipped

    reliable = confidence_band not in UNRELIABLE_CONFIDENCE_BANDS

    if risk_band == "CRITICAL":
        return "URGENT_REVIEW" if reliable else "HIGH_REVIEW"

    if risk_band == "HIGH":
        return "HIGH_REVIEW"

    if risk_band == "MEDIUM":
        if not reliable or disagreement_flag:
            return "HIGH_REVIEW"
        return "STANDARD_REVIEW"

    # risk_band == "LOW"
    if not reliable:
        # A "low risk" verdict we cannot trust is not the same as an
        # actually-low-risk claim - still worth a standard look.
        return "STANDARD_REVIEW"
    return "LOW_REVIEW"
