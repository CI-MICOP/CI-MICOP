from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field

from app.services import claim_copy_retention


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

    # Derived from Document_Type, not a column: False for RC / licence /
    # policy copies, whose file is not kept (services/claim_copy_retention.py).
    @computed_field
    @property
    def Copy_Retained(self) -> bool:
        return claim_copy_retention.is_copy_retained(self.Document_Type)
