"""Business logic for a Surveyor recording a repair estimate.

Mirrors the existing services/vehicle_damage_creation.py pattern: the
router stays a thin HTTP wrapper, and the ownership check, Vehicle_ID
derivation, and ID generation live here. See
docs/project_documentation/SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md.

No cost-consistency rule is enforced between Repair_Cost and
Parts_Cost + Labour_Cost + Painting_Cost: the approved dataset itself
shows these never exactly reconcile (all 654 real rows differ, by
amounts from a few rupees to tens of thousands), so inventing a
tolerance check here would be an arbitrary business rule unsupported
by the project's own data - not a deterministic validation.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.crud import repair_estimate as crud_estimate
from app.db_models.repair_estimate import RepairEstimate
from app.schemas.surveyor import RepairEstimateCreate
from app.services.claim_access import get_claim_assigned_to_surveyor_or_403


def create_repair_estimate_for_surveyor(
    db: Session, employee_id: str, payload: RepairEstimateCreate
) -> RepairEstimate:
    claim = get_claim_assigned_to_surveyor_or_403(db, payload.Claim_ID, employee_id)

    estimate = RepairEstimate(
        Estimate_ID=crud_estimate.generate_estimate_id(db),
        Claim_ID=claim.Claim_ID,
        # Derived from the claim, never trusted from the browser.
        Vehicle_ID=claim.Vehicle_ID,
        Garage_ID=payload.Garage_ID,
        Estimate_Date=payload.Estimate_Date,
        Repair_Estimate=payload.Repair_Estimate,
        Repair_Cost=payload.Repair_Cost,
        Parts_Cost=payload.Parts_Cost,
        Labour_Cost=payload.Labour_Cost,
        Painting_Cost=payload.Painting_Cost,
        Replacement_Parts_Count=payload.Replacement_Parts_Count,
        Repaired_Parts_Count=payload.Repaired_Parts_Count,
        Estimated_Repair_Days=payload.Estimated_Repair_Days,
        # 0 = "not yet available" (never occurs in the real dataset for a
        # completed repair - real values start at 3 days), not a claim
        # that the repair took zero days. See schema docstring.
        Actual_Repair_Days=payload.Actual_Repair_Days if payload.Actual_Repair_Days is not None else 0,
        # No leakage/anomaly-detection AI is connected yet. False is the
        # honest "not flagged" default, never an AI-generated result -
        # this endpoint performs no fraud/anomaly analysis (see
        # docs/project_documentation/SURVEYOR_REPAIR_ESTIMATE_WORKFLOW.md).
        Excessive_Claim_Amount_Indicator=False,
        # 0.0000 = "not yet analyzed", never a real anomaly score.
        Estimate_Anomaly_Score=Decimal("0.0000"),
    )
    crud_estimate.create(db, estimate)
    db.commit()
    db.refresh(estimate)
    return estimate
