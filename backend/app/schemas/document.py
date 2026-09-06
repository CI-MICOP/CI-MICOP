from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Document_ID: str
    Claim_ID: str
    Document_Type: str
    Document_Name: str
    Document_Submitted_Date: date
    Document_Status: str
    OCR_Confidence_Score: Decimal
    Extracted_Text: str
    Document_Completeness: Decimal
    Document_Mismatch_Indicator: bool
    Verification_Status: str
