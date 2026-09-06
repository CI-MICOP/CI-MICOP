from sqlalchemy import Boolean, Column, Date, ForeignKey, Numeric, String

from app.db.base_class import Base


class Policy(Base):
    __tablename__ = "policies"

    Policy_ID = Column(String(30), primary_key=True)
    Customer_ID = Column(String(30), ForeignKey("customers.Customer_ID"), nullable=False, index=True)
    Vehicle_ID = Column(String(30), ForeignKey("vehicles.Vehicle_ID"), nullable=False, index=True)
    Policy_Number = Column(String(30), nullable=False, unique=True)
    Policy_Type = Column(String(30), nullable=False)
    Policy_Code = Column(String(20), nullable=False)
    Coverage_Type = Column(String(30), nullable=False)
    Class_Code = Column(String(20), nullable=False)
    Policy_Start_Date = Column(Date, nullable=False)
    Policy_End_Date = Column(Date, nullable=False)
    Policy_Year = Column(String(10), nullable=False)
    Premium_Amount = Column(Numeric(14, 2), nullable=False)
    Sum_Insured = Column(Numeric(14, 2), nullable=False)
    IDV = Column(Numeric(14, 2), nullable=False)
    Deductible_Amount = Column(Numeric(14, 2), nullable=False)
    No_Claim_Bonus = Column(Numeric(5, 2), nullable=False)
    NCB_Flag = Column(Boolean, nullable=False)
    Policy_Status = Column(String(30), nullable=False, index=True)
    Renewal_Status = Column(String(30), nullable=False)
    Office_Code = Column(String(20), nullable=False)
    Endorsement_Flag = Column(Boolean, nullable=False)
    Endorsement_Number = Column(String(30), nullable=True)
    Anti_Theft_Discount_Flag = Column(Boolean, nullable=False)
    Auto_Association_Discount_Flag = Column(Boolean, nullable=False)
    Voluntary_Excess_Discount_Flag = Column(Boolean, nullable=False)
    Vintage_Car_Discount_Flag = Column(Boolean, nullable=False)
    Own_Premises_Discount_Flag = Column(Boolean, nullable=False)
    Special_Design_Discount_Flag = Column(Boolean, nullable=False)
    Side_Car_Discount_Flag = Column(Boolean, nullable=False)
    Special_Rating_Discount_Flag = Column(Boolean, nullable=False)
    TPPD_Statutory_Cover_Flag = Column(Boolean, nullable=False)
