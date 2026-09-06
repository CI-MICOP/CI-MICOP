from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String, Text

from app.db.base_class import Base


class SurveyorInspection(Base):
    """No separate Surveyor table. Surveyor_ID references
    authentication_users.Employee_ID (not User_ID - see Step 2 report:
    the spec's literal wording named User_ID, but only Employee_ID values
    actually match Surveyor_ID in the dataset)."""

    __tablename__ = "surveyor_inspections"

    Inspection_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Surveyor_ID = Column(
        String(30),
        ForeignKey("authentication_users.Employee_ID"),
        nullable=False,
        index=True,
    )
    Inspection_Date = Column(Date, nullable=False)
    Inspection_Location = Column(Text, nullable=False)
    Vehicle_Condition = Column(String(30), nullable=False)
    # Stored as-is from the dataset ('Yes'/'No' text, not a boolean flag).
    Damage_Observed = Column(String(10), nullable=False)
    Damage_Severity = Column(String(30), nullable=False)
    Parts_Required = Column(Integer, nullable=False)
    Repair_Recommendation = Column(String(30), nullable=False)
    Surveyor_Comments = Column(Text, nullable=False)
    Inspection_Status = Column(String(30), nullable=False)
    Survey_Report_Submitted = Column(Boolean, nullable=False)
    Surveyor_Confidence_Score = Column(Numeric(5, 4), nullable=False)
