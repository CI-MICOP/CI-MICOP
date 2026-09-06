from sqlalchemy import Boolean, Column, ForeignKey, Numeric, String, Text

from app.db.base_class import Base


class VehicleDamage(Base):
    __tablename__ = "vehicle_damage"

    Damage_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Vehicle_ID = Column(String(30), ForeignKey("vehicles.Vehicle_ID"), nullable=False, index=True)
    Damage_Type = Column(String(50), nullable=False)
    Damaged_Part = Column(String(50), nullable=False)
    Damage_Severity = Column(String(30), nullable=False)
    Damage_Location = Column(String(30), nullable=False)
    Estimated_Damage_Cost = Column(Numeric(14, 2), nullable=False)
    Repair_or_Replace = Column(String(20), nullable=False)
    Photo_Evidence_Available = Column(Boolean, nullable=False)
    Vehicle_Damage_Mismatch_Indicator = Column(Boolean, nullable=False)
    Damage_Description = Column(Text, nullable=False)
