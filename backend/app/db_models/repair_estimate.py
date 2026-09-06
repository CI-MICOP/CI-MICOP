from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String

from app.db.base_class import Base


class RepairEstimate(Base):
    __tablename__ = "repair_estimates"

    Estimate_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Vehicle_ID = Column(String(30), ForeignKey("vehicles.Vehicle_ID"), nullable=False, index=True)
    # Garage identifier only - no Garage table per the approved design.
    Garage_ID = Column(String(30), nullable=False, index=True)
    Estimate_Date = Column(Date, nullable=False)
    Repair_Estimate = Column(Numeric(14, 2), nullable=False)
    Repair_Cost = Column(Numeric(14, 2), nullable=False)
    Parts_Cost = Column(Numeric(14, 2), nullable=False)
    Labour_Cost = Column(Numeric(14, 2), nullable=False)
    Painting_Cost = Column(Numeric(14, 2), nullable=False)
    Replacement_Parts_Count = Column(Integer, nullable=False)
    Repaired_Parts_Count = Column(Integer, nullable=False)
    Estimated_Repair_Days = Column(Integer, nullable=False)
    Actual_Repair_Days = Column(Integer, nullable=False)
    Excessive_Claim_Amount_Indicator = Column(Boolean, nullable=False)
    Estimate_Anomaly_Score = Column(Numeric(8, 4), nullable=False)
