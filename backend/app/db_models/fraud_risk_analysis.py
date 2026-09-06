from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String

from app.db.base_class import Base


class FraudRiskAnalysis(Base):
    """Score ranges are intentionally not constrained to today's 0-100 /
    0-1 scale (see Step 2 instructions: the ML system must support
    changing datasets and scoring approaches later)."""

    __tablename__ = "fraud_risk_analysis"

    Risk_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Duplicate_Claim_Indicator = Column(Boolean, nullable=False)
    Previous_Similar_Claim = Column(Boolean, nullable=False)
    Suspicious_Garage_Indicator = Column(Boolean, nullable=False)
    Claim_Immediately_After_Policy_Indicator = Column(Boolean, nullable=False)
    Excessive_Claim_Amount_Indicator = Column(Boolean, nullable=False)
    Document_Mismatch_Indicator = Column(Boolean, nullable=False)
    Vehicle_Damage_Mismatch_Indicator = Column(Boolean, nullable=False)
    Accident_Details_Mismatch_Indicator = Column(Boolean, nullable=False)
    Evidence_Reuse_Indicator = Column(Boolean, nullable=False)
    Fraud_Risk_Score = Column(Numeric(6, 2), nullable=False)
    Anomaly_Score = Column(Numeric(8, 4), nullable=False)
    Overall_Risk_Score = Column(Numeric(6, 2), nullable=False)
    Risk_Category = Column(String(20), nullable=False, index=True)
    # Binary label today (0/1); kept as Integer rather than Boolean so a
    # future multi-class labeling scheme does not require a type change.
    Fraud_Label = Column(Integer, nullable=False)
