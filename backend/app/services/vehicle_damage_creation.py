"""Business logic for a Surveyor recording a vehicle-damage observation.

Mirrors the existing services/inspection_creation.py pattern: the router
stays a thin HTTP wrapper, and the ownership check, Vehicle_ID
derivation, and ID generation live here. See
docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud import vehicle_damage as crud_damage
from app.db_models.vehicle_damage import VehicleDamage
from app.schemas.surveyor import VehicleDamageCreate
from app.services import surveyor_workflow
from app.services.claim_access import get_claim_assigned_to_surveyor_or_403


def create_vehicle_damage_for_surveyor(
    db: Session, employee_id: str, payload: VehicleDamageCreate
) -> VehicleDamage:
    claim = get_claim_assigned_to_surveyor_or_403(db, payload.Claim_ID, employee_id)
    # An active (not submitted) inspection whose scheduled time has arrived,
    # with the Inspection step complete - see services/surveyor_workflow.py.
    surveyor_workflow.require_writable_step(db, payload.Claim_ID, employee_id, surveyor_workflow.STEP_DAMAGE)

    damage = VehicleDamage(
        Damage_ID=crud_damage.generate_damage_id(db),
        Claim_ID=claim.Claim_ID,
        # Derived from the claim, never trusted from the browser.
        Vehicle_ID=claim.Vehicle_ID,
        Damage_Type=payload.Damage_Type,
        Damaged_Part=payload.Damaged_Part,
        Damage_Severity=payload.Damage_Severity,
        Damage_Location=payload.Damage_Location,
        Estimated_Damage_Cost=payload.Estimated_Damage_Cost,
        Repair_or_Replace=payload.Repair_or_Replace,
        Photo_Evidence_Available=payload.Photo_Evidence_Available,
        # No automated cross-checking is connected yet - False is the
        # honest "not flagged" default for a manually recorded
        # observation, never an AI-generated result. See the
        # documentation for why this is not fabricated as a real signal.
        Vehicle_Damage_Mismatch_Indicator=False,
        Damage_Description=payload.Damage_Description,
    )
    crud_damage.create(db, damage)
    db.commit()
    db.refresh(damage)
    return damage
