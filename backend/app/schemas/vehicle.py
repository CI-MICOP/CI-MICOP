from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Vehicle_ID: str
    Customer_ID: str
    Policy_ID: str | None
    Vehicle_Type: str
    Vehicle_Subtype: str | None
    Registration_Number: str
    Chassis_Number: str
    Engine_Number: str
    Vehicle_Color: str
    Make: str
    Make_Code: str
    Model: str
    Variant: str
    Manufacturing_Year: int
    Registration_Year: int
    Vehicle_Age: int
    Fuel_Type: str
    Engine_CC: int
    CC_PCC_GVW_Code: str
    Vehicle_Value: Decimal
    Usage_Type: str
    GVW_KG: int | None
    Load_Capacity_KG: int | None
    Seating_Capacity: int
    Permit_Code: str | None
    Nature_of_Goods_Code: str | None
    Road_Type_Code: str
    Vehicle_Driven_By_Code: str
    RTA_Location_Code: str
    Class_Code: str
    Zone_Code: str
    Previous_Claim_Count: int
    Policy_Start_Date: date
    Policy_End_Date: date
