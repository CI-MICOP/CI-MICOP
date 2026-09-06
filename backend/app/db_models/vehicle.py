from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String

from app.db.base_class import Base


class Vehicle(Base):
    """Vehicles table.

    vehicles.Policy_ID and policies.Vehicle_ID form a circular reference.
    This FK is created with use_alter=True so SQLAlchemy (and the Alembic
    migration) create both tables first and add this constraint via a
    separate ALTER TABLE afterward - see Step 2 report for the full
    migration sequence.
    """

    __tablename__ = "vehicles"

    Vehicle_ID = Column(String(30), primary_key=True)
    Customer_ID = Column(String(30), ForeignKey("customers.Customer_ID"), nullable=False, index=True)
    Policy_ID = Column(
        String(30),
        ForeignKey("policies.Policy_ID", use_alter=True, name="fk_vehicles_policy_id"),
        nullable=True,
        index=True,
    )
    Vehicle_Type = Column(String(50), nullable=False)
    # 100% blank in the current dataset; kept nullable per spec.
    Vehicle_Subtype = Column(String(50), nullable=True)
    Registration_Number = Column(String(30), nullable=False, unique=True)
    Chassis_Number = Column(String(30), nullable=False, unique=True)
    Engine_Number = Column(String(30), nullable=False, unique=True)
    Vehicle_Color = Column(String(30), nullable=False)
    Make = Column(String(50), nullable=False)
    Make_Code = Column(String(20), nullable=False)
    Model = Column(String(50), nullable=False)
    Variant = Column(String(30), nullable=False)
    Manufacturing_Year = Column(Integer, nullable=False)
    Registration_Year = Column(Integer, nullable=False)
    Vehicle_Age = Column(Integer, nullable=False)
    Fuel_Type = Column(String(20), nullable=False)
    Engine_CC = Column(Integer, nullable=False)
    CC_PCC_GVW_Code = Column(String(20), nullable=False)
    Vehicle_Value = Column(Numeric(14, 2), nullable=False)
    Usage_Type = Column(String(30), nullable=False)
    # Only applicable to commercial/heavy vehicles - nullable per spec.
    GVW_KG = Column(Integer, nullable=True)
    Load_Capacity_KG = Column(Integer, nullable=True)
    Seating_Capacity = Column(Integer, nullable=False)
    Permit_Code = Column(String(20), nullable=True)
    Nature_of_Goods_Code = Column(String(20), nullable=True)
    Road_Type_Code = Column(String(20), nullable=False)
    Vehicle_Driven_By_Code = Column(String(20), nullable=False)
    RTA_Location_Code = Column(String(20), nullable=False)
    Class_Code = Column(String(20), nullable=False)
    Zone_Code = Column(String(20), nullable=False)
    Previous_Claim_Count = Column(Integer, nullable=False, default=0)
    Policy_Start_Date = Column(Date, nullable=False)
    Policy_End_Date = Column(Date, nullable=False)
