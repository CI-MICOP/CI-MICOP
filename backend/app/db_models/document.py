from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String, Text

from app.db.base_class import Base


class Document(Base):
    """One-to-many with claims: multiple documents per claim (confirmed
    by the dataset - 3,936 rows across 654 claims).

    Claim_ID is nullable for one additional case: an RC / Driving Licence /
    Insurance Policy identity document imported directly onto an existing
    customer (and, where applicable, their vehicle/policy) ahead of any
    claim - see services/document_import.py. Every such row still carries
    Customer_ID (and Vehicle_ID or Policy_ID where relevant) so it can be
    looked up without a claim; every claim-scoped document created through
    the existing upload flow is unaffected and keeps Claim_ID set with
    these new columns left null.
    """

    __tablename__ = "documents"

    Document_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=True, index=True)
    Document_Type = Column(String(50), nullable=False)
    Document_Name = Column(String(255), nullable=False)
    Document_Submitted_Date = Column(Date, nullable=False)
    Document_Status = Column(String(30), nullable=False)
    OCR_Confidence_Score = Column(Numeric(5, 4), nullable=False)
    # Extracted OCR text only - actual document files are not stored here.
    Extracted_Text = Column(Text, nullable=False)
    Document_Completeness = Column(Numeric(5, 4), nullable=False)
    Document_Mismatch_Indicator = Column(Boolean, nullable=False)
    Verification_Status = Column(String(30), nullable=False)

    # Only ever set for a claim-independent identity document import
    # (services/document_import.py). Null for every ordinary claim document.
    Customer_ID = Column(String(30), ForeignKey("customers.Customer_ID"), nullable=True, index=True)
    Vehicle_ID = Column(String(30), ForeignKey("vehicles.Vehicle_ID"), nullable=True)
    Policy_ID = Column(String(30), ForeignKey("policies.Policy_ID"), nullable=True)
    Document_Expiry_Date = Column(Date, nullable=True)
    # Free-text issuer/source note from the import manifest (e.g. "RTA Chennai").
    Issuer_Reference = Column(String(255), nullable=True)
    # Who uploaded/imported this row - the acting account's User_ID. Null
    # for documents created before this column existed.
    Uploaded_By = Column(String(30), ForeignKey("authentication_users.User_ID"), nullable=True)
