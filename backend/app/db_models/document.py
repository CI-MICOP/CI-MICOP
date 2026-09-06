from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String, Text

from app.db.base_class import Base


class Document(Base):
    """One-to-many with claims: multiple documents per claim (confirmed
    by the dataset - 3,936 rows across 654 claims)."""

    __tablename__ = "documents"

    Document_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
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
