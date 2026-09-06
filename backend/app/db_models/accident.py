from sqlalchemy import Boolean, Column, Date, ForeignKey, String, Text, Time

from app.db.base_class import Base


class Accident(Base):
    """One-to-many with claims (no UNIQUE on Claim_ID) - the current
    dataset happens to have exactly one accident per claim, but the
    schema keeps this flexible per Step 2 instructions. See report."""

    __tablename__ = "accidents"

    Accident_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Accident_Date = Column(Date, nullable=False)
    Accident_Time = Column(Time, nullable=False)
    Accident_Location = Column(Text, nullable=False)
    Accident_City = Column(String(100), nullable=False)
    Accident_State = Column(String(100), nullable=False)
    Accident_Pincode = Column(String(10), nullable=False)
    Accident_Type = Column(String(50), nullable=False)
    Accident_Description = Column(Text, nullable=False)
    Weather_Condition = Column(String(30), nullable=False)
    Road_Condition = Column(String(30), nullable=False)
    Road_Type_Code = Column(String(20), nullable=False)
    Police_Report_Available = Column(Boolean, nullable=False)
    FIR_Number = Column(String(30), nullable=True)
    Third_Party_Involved = Column(Boolean, nullable=False)
    Injury_Reported = Column(Boolean, nullable=False)
    Witness_Available = Column(Boolean, nullable=False)
