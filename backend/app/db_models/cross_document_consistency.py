from sqlalchemy import Boolean, Column, ForeignKey, Numeric, String

from app.db.base_class import Base


class CrossDocumentConsistency(Base):
    __tablename__ = "cross_document_consistency"

    Consistency_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Customer_Statement_Match = Column(String(20), nullable=False)
    FIR_Match = Column(String(20), nullable=False)
    Surveyor_Report_Match = Column(String(20), nullable=False)
    Repair_Estimate_Match = Column(String(20), nullable=False)
    Accident_Date_Match = Column(String(20), nullable=False)
    Accident_Location_Match = Column(String(20), nullable=False)
    Vehicle_Details_Match = Column(String(20), nullable=False)
    Damage_Description_Match = Column(String(20), nullable=False)
    Claim_Amount_Match = Column(String(20), nullable=False)
    Document_Consistency_Score = Column(Numeric(5, 4), nullable=False)
    Document_Mismatch_Indicator = Column(Boolean, nullable=False)
    Accident_Details_Mismatch_Indicator = Column(Boolean, nullable=False)
    Vehicle_Damage_Mismatch_Indicator = Column(Boolean, nullable=False)
    Overall_Consistency_Status = Column(String(20), nullable=False)
