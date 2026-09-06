from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    """Authentication user, excluding Password_Hash."""

    model_config = ConfigDict(from_attributes=True)

    User_ID: str
    Username: str
    Role: str
    Customer_ID: str | None
    Employee_ID: str | None
    Email: str
    Phone: str
    Account_Status: str
    Login_Status: str
    Last_Login: datetime | None
    Created_Date: date
    Failed_Login_Count: int
    Permission_Level: int
