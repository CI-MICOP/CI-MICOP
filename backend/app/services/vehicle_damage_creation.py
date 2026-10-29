"""Business logic for a Surveyor recording a vehicle-damage observation.

Mirrors the existing services/inspection_creation.py pattern: the router
stays a thin HTTP wrapper, and the ownership check, Vehicle_ID
derivation, and ID generation live here. See
docs/project_documentation/SURVEYOR_DAMAGE_AND_EVIDENCE_WORKFLOW.md.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import vehicle_damage as crud_damage
from app.db_models.vehicle_damage import VehicleDamage
from app.schemas.surveyor import VehicleDamageCreate, VehicleDamageUpdate
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


def update_vehicle_damage_for_surveyor(
    db: Session, employee_id: str, damage_id: str, payload: VehicleDamageUpdate
) -> VehicleDamage:
    """Edits an existing vehicle-damage record in place - the "Correct
    this step" flow. Never creates a new row: the record is found by its
    own Damage_ID, and every ownership/schedule/step check is re-derived
    from that record's own Claim_ID (never from anything the browser
    could supply), via the same require_writable_step used for creation -
    so an unassigned surveyor, a claim before its scheduled date, a
    submitted report, or a step not open for correction are all rejected
    exactly as they would be for a new record."""
    damage = crud_damage.get(db, damage_id)
    if damage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle damage record not found")

    surveyor_workflow.require_writable_step(db, damage.Claim_ID, employee_id, surveyor_workflow.STEP_DAMAGE)

    try:
        damage.Damage_Type = payload.Damage_Type
        damage.Damaged_Part = payload.Damaged_Part
        damage.Damage_Severity = payload.Damage_Severity
        damage.Damage_Location = payload.Damage_Location
        damage.Estimated_Damage_Cost = payload.Estimated_Damage_Cost
        damage.Repair_or_Replace = payload.Repair_or_Replace
        damage.Photo_Evidence_Available = payload.Photo_Evidence_Available
        damage.Damage_Description = payload.Damage_Description
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(damage)
    return damage
