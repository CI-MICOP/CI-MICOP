from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String, Text

from app.db.base_class import Base


class Claim(Base):
    __tablename__ = "claims"

    Claim_ID = Column(String(30), primary_key=True)
    Policy_ID = Column(String(30), ForeignKey("policies.Policy_ID"), nullable=False, index=True)
    Customer_ID = Column(String(30), ForeignKey("customers.Customer_ID"), nullable=False, index=True)
    Vehicle_ID = Column(String(30), ForeignKey("vehicles.Vehicle_ID"), nullable=False, index=True)
    Claim_Number = Column(String(30), nullable=False, unique=True)
    Claim_Number_Child = Column(String(30), nullable=True)
    Claim_Date = Column(Date, nullable=False, index=True)
    Claim_Year = Column(String(10), nullable=False)
    Claim_Type = Column(String(30), nullable=False)
    Claim_Amount = Column(Numeric(14, 2), nullable=False)
    Approved_Amount = Column(Numeric(14, 2), nullable=False)
    Claim_Status = Column(String(30), nullable=False, index=True)
    Claim_Description = Column(Text, nullable=False)
    Claims_History_Code = Column(String(10), nullable=False)
    Incurred_Claims_Code = Column(String(10), nullable=False)
    Nature_of_Loss_Code = Column(String(10), nullable=False)
    Insurer_NOL_Code = Column(String(20), nullable=False)
    TPPD_Statutory_Cover_Flag = Column(Boolean, nullable=False)
    Claim_Intimation_Date = Column(Date, nullable=False)
    Date_of_Disbursement = Column(Date, nullable=False)
    Place_of_Accident = Column(String(100), nullable=False)
    Accident_Pincode = Column(String(10), nullable=False)
    Claim_Processing_Days = Column(Integer, nullable=False)
    Repair_Duration_Days = Column(Integer, nullable=False)
    Final_Decision = Column(String(30), nullable=False)
    Decision_Date = Column(Date, nullable=False)
    Decision_Reason = Column(Text, nullable=False)

    # TP (Third Party) fields - duplicated in the separate tp_claims table
    # per the approved 15-table design (see Step 2 report, Table 15).
    TP_Amount_Claimed = Column(Numeric(14, 2), nullable=False)
    TP_Claims_Paid = Column(Numeric(14, 2), nullable=False)
    TP_Awards_Paid = Column(Numeric(14, 2), nullable=False)
    TP_Expenses_Paid = Column(Numeric(14, 2), nullable=False)
    TP_Interest_Paid = Column(Numeric(14, 2), nullable=False)
    Wider_Legal_Liability_Amount = Column(Numeric(14, 2), nullable=False)
    PA_Owner_Driver_Amount = Column(Numeric(14, 2), nullable=False)
    PA_Others_Amount = Column(Numeric(14, 2), nullable=False)
    Nature_of_Injury_Code = Column(String(10), nullable=False)
    Interim_Award_Flag = Column(Boolean, nullable=False)
    Settlement_Basis_Code = Column(String(10), nullable=False)
    Fatal_NonFatal_Flag = Column(Boolean, nullable=False)
    Open_Provision_Main = Column(Numeric(14, 2), nullable=False)
    Open_Provision_Expenses = Column(Numeric(14, 2), nullable=False)
    Open_Provision_Interest = Column(Numeric(14, 2), nullable=False)
    Closing_Provision_Main = Column(Numeric(14, 2), nullable=False)
    Closing_Provision_Expenses = Column(Numeric(14, 2), nullable=False)
    Closing_Provision_Interest = Column(Numeric(14, 2), nullable=False)
