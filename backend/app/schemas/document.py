from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field

from app.services import document_storage


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Document_ID: str
    Claim_ID: str | None
    Document_Type: str
    Document_Name: str
    Document_Submitted_Date: date
    Document_Status: str
    OCR_Confidence_Score: Decimal
    Extracted_Text: str
    Document_Completeness: Decimal
    Document_Mismatch_Indicator: bool
    Verification_Status: str
    # Only set for a claim-independent identity document import
    # (services/document_import.py); null for every ordinary claim document.
    Customer_ID: str | None = None

    # Whether this document's own file actually exists in storage - checked
    # per document, not assumed from its type (services/document_upload.py
    # now stores RC / licence / policy copies too, so a type-based guess
    # would be wrong for a new one and for an old one alike). Not a column.
    @computed_field
    @property
    def Copy_Retained(self) -> bool:
        owner_id = self.Claim_ID or self.Customer_ID
        if not owner_id:
            return False
        try:
            path = document_storage.storage_path_for(owner_id, self.Document_ID, self.Document_Name)
        except ValueError:
            return False
        return path.exists()
