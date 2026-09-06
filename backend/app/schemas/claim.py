from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
