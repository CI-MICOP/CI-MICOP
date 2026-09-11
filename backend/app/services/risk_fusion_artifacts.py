"""Loads the Step 5.4 risk-fusion research-prototype artifacts from
disk: the same already-computed, already-verified files
frontend/src/data/aiRiskFusionDemo.json was hand-exported from (see
docs/project_documentation/AI_OFFICER_INTEGRATION.md, Section 2).

This module only reads static files with the standard-library csv/json
modules (no pandas - not a declared backend dependency, and unnecessary
for 654 simple rows). It never executes ai_ml/ pipeline code and never
retrains or recomputes anything: `ai_ml/experiments/
run_risk_fusion_experiment.py` (Step 5.4, unmodified) already produced
these files once. Results are cached in memory after the first read
since the underlying files are static for the life of the process.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.core.config import settings

_scores_cache: dict[str, dict] | None = None
_examples_cache: dict[str, dict] | None = None

_EXAMPLE_FILENAMES = (
    "high_risk_high_confidence.json",
    "high_risk_low_confidence.json",
    "low_risk_high_confidence.json",
    "signal_disagreement.json",
)


def _scores_path() -> Path:
    return Path(settings.RISK_FUSION_ARTIFACTS_ROOT) / "risk_fusion" / "full_dataset_risk_fusion_scores.csv"


def _explanations_dir() -> Path:
    return Path(settings.RISK_FUSION_ARTIFACTS_ROOT) / "risk_fusion_explanations"


def _load_scores() -> dict[str, dict]:
    global _scores_cache
    if _scores_cache is not None:
        return _scores_cache

    scores: dict[str, dict] = {}
    path = _scores_path()
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                reason_codes = [c for c in (row.get("reason_codes") or "").split(",") if c]
                scores[row["claim_id"]] = {
                    "overall_risk_score": float(row["overall_risk_score"]),
                    "risk_band": row["risk_band"],
                    "confidence_score": float(row["confidence_score"]),
                    "confidence_band": row["confidence_band"],
                    "review_priority": row["review_priority"],
                    "reason_codes": reason_codes,
                    "contributing_signals": int(row["contributing_signals"]),
                    "unavailable_signals": int(row["unavailable_signals"]),
                }
    _scores_cache = scores
    return scores


def _load_examples() -> dict[str, dict]:
    global _examples_cache
    if _examples_cache is not None:
        return _examples_cache

    examples: dict[str, dict] = {}
    directory = _explanations_dir()
    for filename in _EXAMPLE_FILENAMES:
        path = directory / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        examples[data["claim_id"]] = data
    _examples_cache = examples
    return examples


def get_risk_fusion_result(claim_id: str) -> dict | None:
    """Returns the Step 5.4 result for this exact Claim_ID, or None if
    the risk-fusion export has no result for it (the common case for a
    live claim - see this module's docstring). When a full per-signal
    breakdown was also generated for this claim (4 of 654), it is merged
    in under "signals"/"explanation"/"uncertainty_reasons"/
    "officer_explanations"/"human_review_required"."""
    summary = _load_scores().get(claim_id)
    if summary is None:
        return None

    result = dict(summary)
    example = _load_examples().get(claim_id)
    if example is not None:
        result["signals"] = example.get("signals", [])
        result["explanation"] = [example["explanation"]] if example.get("explanation") else []
        result["uncertainty_reasons"] = example.get("uncertainty_reasons", [])
        result["officer_explanations"] = example.get("officer_explanations", [])
        result["human_review_required"] = example.get("human_review_required", True)
        result["has_full_breakdown"] = True
    else:
        result["signals"] = []
        result["explanation"] = []
        result["uncertainty_reasons"] = []
        result["officer_explanations"] = []
        result["human_review_required"] = True
        result["has_full_breakdown"] = False
    return result
