"""Schemas for claim-child tables, used to assemble the richer claim
detail views returned to Surveyor / Claims Officer / Admin."""

from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Accident_ID: str
    Claim_ID: str
    Accident_Date: date
    Accident_Time: time
    Accident_Location: str
    Accident_City: str
    Accident_State: str
    Accident_Pincode: str
    Accident_Type: str
    Accident_Description: str
    Weather_Condition: str
    Road_Condition: str
    Road_Type_Code: str
    Police_Report_Available: bool
    FIR_Number: str | None
    Third_Party_Involved: bool
    Injury_Reported: bool
    Witness_Available: bool


class VehicleDamageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Damage_ID: str
    Claim_ID: str
    Vehicle_ID: str
    Damage_Type: str
    Damaged_Part: str
    Damage_Severity: str
    Damage_Location: str
    Estimated_Damage_Cost: Decimal
    Repair_or_Replace: str
    Photo_Evidence_Available: bool
    Vehicle_Damage_Mismatch_Indicator: bool
    Damage_Description: str


class RepairEstimateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Estimate_ID: str
    Claim_ID: str
    Vehicle_ID: str
    Garage_ID: str
    Estimate_Date: date
    Repair_Estimate: Decimal
    Repair_Cost: Decimal
    Parts_Cost: Decimal
    Labour_Cost: Decimal
    Painting_Cost: Decimal
    Replacement_Parts_Count: int
    Repaired_Parts_Count: int
    Estimated_Repair_Days: int
    Actual_Repair_Days: int
    Excessive_Claim_Amount_Indicator: bool
    Estimate_Anomaly_Score: Decimal


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Evidence_ID: str
    Claim_ID: str
    Evidence_Type: str
    File_Name: str
    Evidence_Date: date
    Evidence_Source: str
    Image_Quality: Decimal
    Vehicle_Damage_Detected: bool
    Damage_Severity: str
    Location_Match: bool
    Duplicate_Evidence_Indicator: bool
    Evidence_Confidence_Score: Decimal
    Verification_Status: str


class CrossDocumentConsistencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Consistency_ID: str
    Claim_ID: str
    Customer_Statement_Match: str
    FIR_Match: str
    Surveyor_Report_Match: str
    Repair_Estimate_Match: str
    Accident_Date_Match: str
    Accident_Location_Match: str
    Vehicle_Details_Match: str
    Damage_Description_Match: str
    Claim_Amount_Match: str
    Document_Consistency_Score: Decimal
    Document_Mismatch_Indicator: bool
    Accident_Details_Mismatch_Indicator: bool
    Vehicle_Damage_Mismatch_Indicator: bool
    Overall_Consistency_Status: str


class FraudRiskAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Risk_ID: str
    Claim_ID: str
    Duplicate_Claim_Indicator: bool
    Previous_Similar_Claim: bool
    Suspicious_Garage_Indicator: bool
    Claim_Immediately_After_Policy_Indicator: bool
    Excessive_Claim_Amount_Indicator: bool
    Document_Mismatch_Indicator: bool
    Vehicle_Damage_Mismatch_Indicator: bool
    Accident_Details_Mismatch_Indicator: bool
    Evidence_Reuse_Indicator: bool
    Fraud_Risk_Score: Decimal
    Anomaly_Score: Decimal
    Overall_Risk_Score: Decimal
    Risk_Category: str
    Fraud_Label: int


class ClaimDecisionAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Audit_ID: str
    Claim_ID: str
    Claims_Officer_ID: str
    AI_Recommendation: str
    AI_Confidence_Score: Decimal
    Human_Review_Required: bool
    Final_Decision: str
    Decision_Reason: str
    Approved_Amount: Decimal
    Decision_Date: date
    Escalation_Status: str
    Escalated_To: str | None
    Officer_Comments: str
    Audit_Action: str


class TPClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    TP_Claim_ID: str
    Claim_ID: str
    TP_Amount_Claimed: Decimal
    TP_Claims_Paid: Decimal
    TP_Awards_Paid: Decimal
    TP_Expenses_Paid: Decimal
    TP_Interest_Paid: Decimal
    Wider_Legal_Liability_Amount: Decimal
    PA_Owner_Driver_Amount: Decimal
    PA_Others_Amount: Decimal
    Open_Provision_Main: Decimal
    Open_Provision_Expenses: Decimal
    Open_Provision_Interest: Decimal
    Closing_Provision_Main: Decimal
    Closing_Provision_Expenses: Decimal
    Closing_Provision_Interest: Decimal
