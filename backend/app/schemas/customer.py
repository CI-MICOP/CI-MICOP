from datetime import date

from pydantic import BaseModel, ConfigDict


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Customer_ID: str
    Customer_Name: str
    Date_of_Birth: date
    Age: int
    Gender: str
    Phone: str
    Email: str
    Address: str
    City: str
    State: str
    Pincode: str
    Occupation: str
    Driving_Experience_Years: int
    Customer_Type: str
    Previous_Claim_Count: int
    Driver_Age_Code: str
    Driver_Experience_Code: str
    Driver_Qualification_Code: str
    Driver_Type_Code: str
