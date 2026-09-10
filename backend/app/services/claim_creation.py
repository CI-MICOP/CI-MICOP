"""Business logic for creating a customer-submitted claim (FNOL).

Mirrors the existing services/claim_access.py pattern: the router stays a
thin HTTP wrapper, and the actual rules - ownership checks, ID generation,
and the safe default values required for the non-nullable processing
columns the customer's form doesn't collect - live here in one place.

See docs/project_documentation/CUSTOMER_CLAIM_SUBMISSION.md for the
documented rationale/limitations behind every default below.
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import accident as crud_accident
from app.crud import claim as crud_claim
from app.crud import customer as crud_customer
from app.crud import policy as crud_policy
from app.crud import vehicle as crud_vehicle
from app.db_models.accident import Accident
from app.db_models.claim import Claim
from app.db_models.policy import Policy
from app.db_models.vehicle import Vehicle
from app.schemas.claim import ClaimCreate

# Project convention (matches seed_dev_data.py), not part of the dataset's
# own codebook - kept here as the single source of truth.
_NATURE_OF_LOSS_CODE_BY_CLAIM_TYPE = {
    "Own Damage": "COL",
    "Theft": "THEFT",
    "Third Party": "TP",
}


def _validate_ownership(db: Session, customer_id: str, payload: ClaimCreate) -> tuple[Policy, Vehicle]:
    policy = crud_policy.get(db, payload.Policy_ID)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    if policy.Customer_ID != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only file a claim against your own policy",
        )

    vehicle = crud_vehicle.get(db, payload.Vehicle_ID)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    if vehicle.Customer_ID != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only file a claim against your own vehicle",
        )

    if policy.Vehicle_ID != vehicle.Vehicle_ID or vehicle.Policy_ID != policy.Policy_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected vehicle is not linked to the selected policy",
        )

    return policy, vehicle


def create_claim_for_customer(db: Session, customer_id: str, payload: ClaimCreate) -> Claim:
    policy, vehicle = _validate_ownership(db, customer_id, payload)
    customer = crud_customer.get(db, customer_id)

    today = date.today()
    claim_id = crud_claim.generate_claim_id(db)
    claim_number = crud_claim.generate_claim_number(db, payload.Claim_Date)

    claims_history_code = "C0" if vehicle.Previous_Claim_Count == 0 else "C1"
    nature_of_loss_code = _NATURE_OF_LOSS_CODE_BY_CLAIM_TYPE.get(payload.Claim_Type, "OTH")
    nature_of_injury_code = "PENDING" if payload.Injury_Reported else "NONE"

    claim = Claim(
        Claim_ID=claim_id,
        Policy_ID=policy.Policy_ID,
        Customer_ID=customer_id,
        Vehicle_ID=vehicle.Vehicle_ID,
        Claim_Number=claim_number,
        Claim_Number_Child=None,
        Claim_Date=payload.Claim_Date,
        Claim_Year=str(payload.Claim_Date.year),
        Claim_Type=payload.Claim_Type,
        Claim_Amount=payload.Claim_Amount,
        Approved_Amount=Decimal("0.00"),
        Claim_Status="Under Review",
        Claim_Description=payload.Claim_Description,
        Claims_History_Code=claims_history_code,
        Incurred_Claims_Code="I1",
        Nature_of_Loss_Code=nature_of_loss_code,
        Insurer_NOL_Code="NOL1",
        TPPD_Statutory_Cover_Flag=policy.TPPD_Statutory_Cover_Flag,
        Claim_Intimation_Date=today,
        # Not a real payment date - the schema has no nullable "not yet
        # disbursed" representation for this non-null column, so a fresh
        # claim gets a neutral placeholder (its own intimation date) rather
        # than a fabricated future date. Must never be read as evidence a
        # disbursement occurred; ClaimOut consumers should key off
        # Claim_Status / Final_Decision instead.
        Date_of_Disbursement=today,
        Place_of_Accident=payload.Place_of_Accident,
        Accident_Pincode=payload.Accident_Pincode,
        Claim_Processing_Days=0,
        Repair_Duration_Days=0,
        Final_Decision="Pending",
        # Same placeholder rationale as Date_of_Disbursement - no decision
        # has actually been made yet.
        Decision_Date=today,
        Decision_Reason="Awaiting Claims Officer review. No decision has been made yet.",
        TP_Amount_Claimed=Decimal("0.00"),
        TP_Claims_Paid=Decimal("0.00"),
        TP_Awards_Paid=Decimal("0.00"),
        TP_Expenses_Paid=Decimal("0.00"),
        TP_Interest_Paid=Decimal("0.00"),
        Wider_Legal_Liability_Amount=Decimal("0.00"),
        PA_Owner_Driver_Amount=Decimal("0.00"),
        PA_Others_Amount=Decimal("0.00"),
        Nature_of_Injury_Code=nature_of_injury_code,
        Interim_Award_Flag=False,
        Settlement_Basis_Code="PENDING",
        Fatal_NonFatal_Flag=False,
        Open_Provision_Main=payload.Claim_Amount,
        Open_Provision_Expenses=Decimal("0.00"),
        Open_Provision_Interest=Decimal("0.00"),
        Closing_Provision_Main=Decimal("0.00"),
        Closing_Provision_Expenses=Decimal("0.00"),
        Closing_Provision_Interest=Decimal("0.00"),
    )

    accident = Accident(
        Accident_ID=crud_accident.generate_accident_id(db),
        Claim_ID=claim_id,
        Accident_Date=payload.Claim_Date,
        Accident_Time=payload.Accident_Time or time(0, 0),
        Accident_Location=payload.Place_of_Accident,
        # No separate city/state fields exist on the FNOL form - Accident_City
        # reuses the free-text place of accident, Accident_State falls back to
        # the customer's registered state. Documented limitation, not fabricated
        # data: both are best-effort, not verified accident-site facts.
        Accident_City=payload.Place_of_Accident[:100],
        Accident_State=customer.State if customer else "Unknown",
        Accident_Pincode=payload.Accident_Pincode,
        Accident_Type="Not Specified",
        Accident_Description=payload.Claim_Description,
        Weather_Condition="Not Reported",
        Road_Condition="Not Reported",
        Road_Type_Code=vehicle.Road_Type_Code,
        Police_Report_Available=payload.Police_Report_Available,
        FIR_Number=payload.FIR_Number,
        Third_Party_Involved=payload.Third_Party_Involved,
        Injury_Reported=payload.Injury_Reported,
        Witness_Available=False,
    )

    try:
        crud_claim.create(db, claim)
        db.flush()
        crud_accident.create(db, accident)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The claim could not be submitted due to an internal error. No claim was saved.",
        ) from exc

    db.refresh(claim)
    return claim
