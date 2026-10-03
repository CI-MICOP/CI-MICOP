from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Real values observed in the approved dataset (see
# ai_ml/model_artifacts/test_set_predictions_and_errors.csv) - the FNOL
# form offers exactly these, so a claim never carries a Claim_Type the
# rest of the project's data/AI pipeline hasn't seen before.
ALLOWED_CLAIM_TYPES = {"Own Damage", "Third Party", "Theft"}


class ClaimCreate(BaseModel):
    """Fields a Customer may submit at First Notice of Loss (FNOL).

    Deliberately excludes every internal/processing field (Approved_Amount,
    Final_Decision, Decision_Date, Decision_Reason, Claim_Processing_Days,
    AI/fraud/audit fields, ...) - those are always server-assigned so a
    claim can never arrive pre-approved or pre-decided from the browser.
    """

    Policy_ID: str
    Vehicle_ID: str
    Claim_Date: date
    Claim_Type: str
    Claim_Amount: Decimal = Field(gt=0)
    Claim_Description: str = Field(min_length=1)
    Place_of_Accident: str = Field(min_length=1, max_length=100)
    Accident_Pincode: str = Field(min_length=1, max_length=10)

    # Optional accident detail already collected by the existing NewClaimPage
    # UI. Police_Station is intentionally not accepted here - the approved
    # accidents table has no column for it (only FIR_Number, a different
    # concept) - see CUSTOMER_CLAIM_SUBMISSION.md limitations.
    Accident_Time: time | None = None
    Third_Party_Involved: bool = False
    Injury_Reported: bool = False
    Police_Report_Available: bool = False
    FIR_Number: str | None = Field(default=None, max_length=30)  # accidents.FIR_Number is VARCHAR(30)

    @field_validator("Claim_Type")
    @classmethod
    def _validate_claim_type(cls, value: str) -> str:
        if value not in ALLOWED_CLAIM_TYPES:
            raise ValueError(f"Claim_Type must be one of {sorted(ALLOWED_CLAIM_TYPES)}")
        return value


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Claim_ID: str
    Policy_ID: str
    Customer_ID: str
    Vehicle_ID: str
    Claim_Number: str
    Claim_Number_Child: str | None
    Claim_Date: date
    Claim_Year: str
    Claim_Type: str
    Claim_Amount: Decimal
    Approved_Amount: Decimal
    Claim_Status: str
    Claim_Description: str
    Claims_History_Code: str
    Incurred_Claims_Code: str
    Nature_of_Loss_Code: str
    Insurer_NOL_Code: str
    TPPD_Statutory_Cover_Flag: bool
    Claim_Intimation_Date: date
    Date_of_Disbursement: date
    Place_of_Accident: str
    Accident_Pincode: str
    Claim_Processing_Days: int
    Repair_Duration_Days: int
    Final_Decision: str
    Decision_Date: date
    Decision_Reason: str
    TP_Amount_Claimed: Decimal
    TP_Claims_Paid: Decimal
    TP_Awards_Paid: Decimal
    TP_Expenses_Paid: Decimal
    TP_Interest_Paid: Decimal
    Wider_Legal_Liability_Amount: Decimal
    PA_Owner_Driver_Amount: Decimal
    PA_Others_Amount: Decimal
    Nature_of_Injury_Code: str
    Interim_Award_Flag: bool
    Settlement_Basis_Code: str
    Fatal_NonFatal_Flag: bool
    Open_Provision_Main: Decimal
    Open_Provision_Expenses: Decimal
    Open_Provision_Interest: Decimal
    Closing_Provision_Main: Decimal
    Closing_Provision_Expenses: Decimal
    Closing_Provision_Interest: Decimal


class ClaimSummaryOut(BaseModel):
    """Lighter shape for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    Claim_ID: str
    Claim_Number: str
    Policy_ID: str
    Customer_ID: str
    Vehicle_ID: str
    Claim_Date: date
    Claim_Type: str
    Claim_Amount: Decimal
    Approved_Amount: Decimal
    Claim_Status: str
    Final_Decision: str
