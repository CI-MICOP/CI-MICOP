"""Aggregates the one-to-many CI-MICOP child tables (documents, evidence)
down to exactly one row per claim, so they can be safely joined onto the
claim-level modeling dataset without multiplying claim rows.

Verified claim-cardinality (see docs/project_documentation/AI_ML_DATASET_AUDIT.md,
Section A) before writing this module:
  - documents:   3936 rows / 654 claims -> avg 6.02, max 8 per claim  -> MUST aggregate
  - evidence:    1301 rows / 654 claims -> avg 1.99, max 3 per claim  -> MUST aggregate
  - accidents, vehicle_damage, repair_estimates, cross_document_consistency,
    fraud_risk_analysis, claim_decision_audit: exactly 1 row per claim (654/654)
    -> safe to left-join directly, no aggregation needed.
  - surveyor_inspections: at most 1 row per claim, but only present for
    531/654 claims (123 claims have none) -> safe to left-join directly;
    the resulting NaNs are a genuine "no inspection yet" signal, not
    something to silently fill in.
  - tp_claims: at most 1 row per claim, present for 186/654 claims (only
    claims with third-party involvement) -> safe to left-join directly.
"""

from __future__ import annotations

import pandas as pd

# Document/evidence type universe is small and fixed in this dataset, so a
# presence/count pivot (rather than free-text aggregation) is the safest
# way to summarize them without inventing categories.
DOCUMENT_TYPES = [
    "Insurance Policy", "Accident Photos", "Repair Estimate", "FIR",
    "Damage Photos", "RC", "Garage Bill", "Driving License",
]
EVIDENCE_TYPES = ["Survey Photo", "Damage Photo", "Accident Photo"]


def aggregate_documents(documents: pd.DataFrame) -> pd.DataFrame:
    """One row per Claim_ID summarizing that claim's documents."""
    grouped = documents.groupby("Claim_ID")

    agg = grouped.agg(
        document_count=("Document_ID", "count"),
        distinct_document_types=("Document_Type", "nunique"),
        document_ocr_confidence_mean=("OCR_Confidence_Score", "mean"),
        document_ocr_confidence_min=("OCR_Confidence_Score", "min"),
        document_completeness_mean=("Document_Completeness", "mean"),
        document_any_mismatch=("Document_Mismatch_Indicator", "max"),
    ).reset_index()

    # One-hot "was this document type present at all for this claim" -
    # a fixed-width, leakage-safe way to capture which documents were
    # submitted without letting the number of rows vary per claim.
    present = (
        documents.assign(_present=1)
        .pivot_table(index="Claim_ID", columns="Document_Type", values="_present", aggfunc="max", fill_value=0)
        .reindex(columns=DOCUMENT_TYPES, fill_value=0)
    )
    present.columns = [f"has_document_{c.replace(' ', '_')}" for c in present.columns]
    present = present.reset_index()

    return agg.merge(present, on="Claim_ID", how="left")


def aggregate_evidence(evidence: pd.DataFrame) -> pd.DataFrame:
    """One row per Claim_ID summarizing that claim's evidence items."""
    grouped = evidence.groupby("Claim_ID")

    agg = grouped.agg(
        evidence_count=("Evidence_ID", "count"),
        distinct_evidence_types=("Evidence_Type", "nunique"),
        evidence_image_quality_mean=("Image_Quality", "mean"),
        evidence_any_damage_detected=("Vehicle_Damage_Detected", "max"),
        evidence_any_duplicate_flag=("Duplicate_Evidence_Indicator", "max"),
        evidence_confidence_mean=("Evidence_Confidence_Score", "mean"),
    ).reset_index()

    present = (
        evidence.assign(_present=1)
        .pivot_table(index="Claim_ID", columns="Evidence_Type", values="_present", aggfunc="max", fill_value=0)
        .reindex(columns=EVIDENCE_TYPES, fill_value=0)
    )
    present.columns = [f"has_evidence_{c.replace(' ', '_')}" for c in present.columns]
    present = present.reset_index()

    return agg.merge(present, on="Claim_ID", how="left")
