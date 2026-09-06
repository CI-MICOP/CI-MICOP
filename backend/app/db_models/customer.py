from sqlalchemy import Column, Date, Integer, String

from app.db.base_class import Base


class Customer(Base):
    __tablename__ = "customers"

    Customer_ID = Column(String(30), primary_key=True)
    Customer_Name = Column(String(150), nullable=False)
    Date_of_Birth = Column(Date, nullable=False)
    Age = Column(Integer, nullable=False)
    Gender = Column(String(20), nullable=False)
    Phone = Column(String(20), nullable=False)
    Email = Column(String(255), nullable=False)
    Address = Column(String(255), nullable=False)
    City = Column(String(100), nullable=False, index=True)
    State = Column(String(100), nullable=False, index=True)
    Pincode = Column(String(10), nullable=False, index=True)
    Occupation = Column(String(50), nullable=False)
    Driving_Experience_Years = Column(Integer, nullable=False)
    Customer_Type = Column(String(30), nullable=False)
    Previous_Claim_Count = Column(Integer, nullable=False, default=0)
    Driver_Age_Code = Column(String(10), nullable=False)
    Driver_Experience_Code = Column(String(10), nullable=False)
    Driver_Qualification_Code = Column(String(10), nullable=False)
    Driver_Type_Code = Column(String(10), nullable=False)
