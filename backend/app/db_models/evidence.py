from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String

from app.db.base_class import Base


class Evidence(Base):
    """One-to-many with claims: multiple evidence items per claim
    (confirmed by the dataset - 1,301 rows across 654 claims)."""

    __tablename__ = "evidence"

    Evidence_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Evidence_Type = Column(String(50), nullable=False)
    # Metadata only - actual image/file binaries are not stored here.
    File_Name = Column(String(255), nullable=False)
    Evidence_Date = Column(Date, nullable=False)
    Evidence_Source = Column(String(30), nullable=False)
    Image_Quality = Column(Numeric(5, 4), nullable=False)
    Vehicle_Damage_Detected = Column(Boolean, nullable=False)
    Damage_Severity = Column(String(30), nullable=False)
    Location_Match = Column(Boolean, nullable=False)
    Duplicate_Evidence_Indicator = Column(Boolean, nullable=False)
    Evidence_Confidence_Score = Column(Numeric(5, 4), nullable=False)
    Verification_Status = Column(String(30), nullable=False)
