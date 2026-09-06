from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SurveyorInspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Inspection_ID: str
    Claim_ID: str
    Surveyor_ID: str
    Inspection_Date: date
    Inspection_Location: str
    Vehicle_Condition: str
    Damage_Observed: str
    Damage_Severity: str
    Parts_Required: int
    Repair_Recommendation: str
    Surveyor_Comments: str
    Inspection_Status: str
    Survey_Report_Submitted: bool
    Surveyor_Confidence_Score: Decimal


class SurveyorInspectionUpdate(BaseModel):
    """Fields a surveyor may update after conducting an inspection.

    All optional - only the fields the surveyor supplies are changed.
    """

    Vehicle_Condition: str | None = None
    Damage_Observed: str | None = None
    Damage_Severity: str | None = None
    Parts_Required: int | None = None
    Repair_Recommendation: str | None = None
    Surveyor_Comments: str | None = None
    Inspection_Status: str | None = None
    Survey_Report_Submitted: bool | None = None
    Surveyor_Confidence_Score: Decimal | None = None
