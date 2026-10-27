"""The survey report: one report representation for both View Report (the
JSON endpoint) and Download Report (the PDF rendered from the same dict by
services/survey_report_pdf.py), so the two cannot disagree.

Completeness rules come from services/surveyor_workflow.py - the same
checks used when the report is submitted. Building a report is read-only:
it never submits, approves or changes anything.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import accident as crud_accident
from app.crud import customer as crud_customer
from app.crud import policy as crud_policy
from app.crud import surveyor_inspection as crud_inspection
from app.crud import vehicle as crud_vehicle
from app.crud import vehicle_damage as crud_vehicle_damage
from app.db_models.surveyor_inspection import SurveyorInspection
from app.schemas.surveyor import (
    DAMAGE_OBSERVED_VALUES,
    DAMAGE_SEVERITY_VALUES,
    PENDING,
    REPAIR_RECOMMENDATION_VALUES,
    VEHICLE_CONDITION_VALUES,
)
from app.services import evidence_capture, surveyor_workflow
from app.services.claim_access import get_claim_assigned_to_surveyor_or_403

_ALLOWED_FINAL_VALUES = {
    "Vehicle_Condition": VEHICLE_CONDITION_VALUES,
    "Damage_Observed": DAMAGE_OBSERVED_VALUES,
    "Damage_Severity": DAMAGE_SEVERITY_VALUES,
    "Repair_Recommendation": REPAIR_RECOMMENDATION_VALUES,
}


def _invalid_stored_values(inspection: SurveyorInspection) -> list[dict]:
    """Stored values that are not allowed options (for example older sample
    data). They are reported as stored, flagged - never corrected here."""
    invalid = []
    for field, allowed in _ALLOWED_FINAL_VALUES.items():
        value = getattr(inspection, field)
        if value != PENDING and value not in allowed:
            invalid.append(
                {"field": field, "label": surveyor_workflow.INSPECTION_FIELD_LABELS[field], "value": value}
            )
    return invalid


def evidence_entry(evidence, inspection: SurveyorInspection | None) -> dict:
    """One evidence row with its capture record (if it was taken with the
    in-app camera). Automated analysis is only reported once it has run; a
    pending row's placeholder zeros are never presented as results."""
    metadata = evidence_capture.read_metadata(evidence)
    analysed = evidence.Verification_Status != PENDING
    return {
        "Evidence_ID": evidence.Evidence_ID,
        "Evidence_Type": evidence.Evidence_Type,
        "Evidence_Date": evidence.Evidence_Date,
        "Evidence_Source": evidence.Evidence_Source,
        "File_Name": evidence.File_Name,
        "Verification_Status": evidence.Verification_Status,
        "analysis": (
            {
                "Image_Quality": evidence.Image_Quality,
                "Vehicle_Damage_Detected": evidence.Vehicle_Damage_Detected,
                "Damage_Severity": evidence.Damage_Severity,
                "Location_Match": evidence.Location_Match,
                "Duplicate_Evidence_Indicator": evidence.Duplicate_Evidence_Indicator,
                "Evidence_Confidence_Score": evidence.Evidence_Confidence_Score,
            }
            if analysed
            else None
        ),
        "capture": evidence_capture.public_view(metadata),
        "qualifying_capture": bool(inspection) and evidence_capture.qualifies_for_inspection(metadata, inspection),
    }


def _build(db: Session, claim, inspection: SurveyorInspection) -> dict:
    customer = crud_customer.get(db, claim.Customer_ID)
    vehicle = crud_vehicle.get(db, claim.Vehicle_ID)
    policy = crud_policy.get(db, claim.Policy_ID)
    damages = crud_vehicle_damage.list_by_claim(db, claim.Claim_ID)

    return {
        "report_status": "Submitted" if inspection.Survey_Report_Submitted else "Draft",
        "generated_at": surveyor_workflow.now_ist().replace(microsecond=0),
        "surveyor": {"Employee_ID": inspection.Surveyor_ID},
        "claim": {
            "Claim_ID": claim.Claim_ID,
            "Claim_Number": claim.Claim_Number,
            "Claim_Date": claim.Claim_Date,
            "Claim_Intimation_Date": claim.Claim_Intimation_Date,
            "Claim_Type": claim.Claim_Type,
            "Claim_Status": claim.Claim_Status,
            "Claim_Amount": claim.Claim_Amount,
            "Claim_Description": claim.Claim_Description,
        },
        # Only what the report needs: no date of birth, contact details or
        # address.
        "customer": (
            {"Customer_ID": customer.Customer_ID, "Customer_Name": customer.Customer_Name} if customer else None
        ),
        "vehicle": (
            {
                "Registration_Number": vehicle.Registration_Number,
                "Make": vehicle.Make,
                "Model": vehicle.Model,
                "Manufacturing_Year": vehicle.Manufacturing_Year,
            }
            if vehicle
            else None
        ),
        "policy": {"Policy_Number": policy.Policy_Number, "Policy_Type": policy.Policy_Type} if policy else None,
        "accidents": [
            {
                "Accident_Date": a.Accident_Date,
                "Accident_Time": a.Accident_Time,
                "Accident_Type": a.Accident_Type,
                "Accident_Location": a.Accident_Location,
                "Accident_City": a.Accident_City,
                "Accident_State": a.Accident_State,
                "Accident_Pincode": a.Accident_Pincode,
                "Accident_Description": a.Accident_Description,
                "Weather_Condition": a.Weather_Condition,
                "Road_Condition": a.Road_Condition,
                "Police_Report_Available": a.Police_Report_Available,
                "FIR_Number": a.FIR_Number,
                "Third_Party_Involved": a.Third_Party_Involved,
                "Injury_Reported": a.Injury_Reported,
                "Witness_Available": a.Witness_Available,
            }
            for a in crud_accident.list_by_claim(db, claim.Claim_ID)
        ],
        "inspection": {
            "Inspection_ID": inspection.Inspection_ID,
            "Inspection_Date": inspection.Inspection_Date,
            "Inspection_Location": inspection.Inspection_Location,
            "Vehicle_Condition": inspection.Vehicle_Condition,
            "Damage_Observed": inspection.Damage_Observed,
            "Damage_Severity": inspection.Damage_Severity,
            "Parts_Required": inspection.Parts_Required,
            "Repair_Recommendation": inspection.Repair_Recommendation,
            "Inspection_Status": inspection.Inspection_Status,
            "Surveyor_Comments": inspection.Surveyor_Comments,
            "Survey_Report_Submitted": inspection.Survey_Report_Submitted,
        },
        "invalid_values": _invalid_stored_values(inspection),
        "vehicle_damage": [
            {
                "Damage_ID": d.Damage_ID,
                "Damage_Type": d.Damage_Type,
                "Damaged_Part": d.Damaged_Part,
                "Damage_Severity": d.Damage_Severity,
                "Damage_Location": d.Damage_Location,
                "Estimated_Damage_Cost": d.Estimated_Damage_Cost,
                "Repair_or_Replace": d.Repair_or_Replace,
                "Photo_Evidence_Available": d.Photo_Evidence_Available,
                "Damage_Description": d.Damage_Description,
            }
            for d in damages
        ],
        "total_estimated_damage_cost": sum((d.Estimated_Damage_Cost for d in damages), Decimal("0")),
        # Surveyor evidence only: this inspection's own camera captures.
        # Customer photos (customer documents, or dataset rows marked
        # "Customer") are never part of the survey report.
        "evidence": [evidence_entry(e, inspection) for e, _ in surveyor_workflow.surveyor_captures(db, inspection)],
        "warnings": surveyor_workflow.consistency_warnings(db, inspection),
        # Submitted reports only: whether the saved records still meet the
        # current submission rules. Reported, never corrected or re-verified.
        "submission_review": surveyor_workflow.submission_review(db, inspection),
    }


def build_survey_report(db: Session, claim_id: str, employee_id: str) -> dict:
    """The report for the assigned surveyor's own current inspection on a
    claim: a Draft once the workflow is complete, or the submitted report."""
    claim = get_claim_assigned_to_surveyor_or_403(db, claim_id, employee_id)
    inspection = surveyor_workflow.own_inspection(crud_inspection.list_by_claim(db, claim_id), employee_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No inspection exists for this claim yet.")
    if not inspection.Survey_Report_Submitted:
        problems = surveyor_workflow.workflow_problems(db, inspection)
        if problems:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The survey report is not available until the workflow is complete. " + " ".join(problems),
            )
    return _build(db, claim, inspection)


def build_submitted_report(db: Session, inspection_id: str, employee_id: str) -> dict:
    """A submitted report from the surveyor's Survey Reports history - only
    their own, and only once submitted."""
    inspection = crud_inspection.get(db, inspection_id)
    if inspection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey report not found.")
    if inspection.Surveyor_ID != employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You may only view your own survey reports.")
    if not inspection.Survey_Report_Submitted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This survey report has not been submitted yet.")
    claim = get_claim_assigned_to_surveyor_or_403(db, inspection.Claim_ID, employee_id)
    return _build(db, claim, inspection)
