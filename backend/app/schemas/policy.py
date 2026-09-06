from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Policy_ID: str
    Customer_ID: str
    Vehicle_ID: str
    Policy_Number: str
    Policy_Type: str
    Policy_Code: str
    Coverage_Type: str
    Class_Code: str
    Policy_Start_Date: date
    Policy_End_Date: date
    Policy_Year: str
    Premium_Amount: Decimal
    Sum_Insured: Decimal
    IDV: Decimal
    Deductible_Amount: Decimal
    No_Claim_Bonus: Decimal
    NCB_Flag: bool
    Policy_Status: str
    Renewal_Status: str
    Office_Code: str
    Endorsement_Flag: bool
    Endorsement_Number: str | None
    Anti_Theft_Discount_Flag: bool
    Auto_Association_Discount_Flag: bool
    Voluntary_Excess_Discount_Flag: bool
    Vintage_Car_Discount_Flag: bool
    Own_Premises_Discount_Flag: bool
    Special_Design_Discount_Flag: bool
    Side_Car_Discount_Flag: bool
    Special_Rating_Discount_Flag: bool
    TPPD_Statutory_Cover_Flag: bool
