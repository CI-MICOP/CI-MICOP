from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Real values observed in the approved dataset
# (ai_ml/datasets/CI_MICOP_15_Tables_Complete/11_surveyor_inspections.xlsx).
# "Pending" is the one addition: a clearly-labeled sentinel meaning "not
# yet assessed", used only for a freshly created inspection - never a real
# inspection conclusion, and never accepted as a final value when a
# survey report is submitted (see routers/surveyor.py's completeness
# check). This mirrors the project's existing "Pending" convention
# already used for Final_Decision/Settlement_Basis_Code on claims.
PENDING = "Pending"
VEHICLE_CONDITION_VALUES = {"Good", "Fair", "Poor"}
DAMAGE_OBSERVED_VALUES = {"Yes", "No"}
DAMAGE_SEVERITY_VALUES = {"Minor", "Moderate", "Severe"}
REPAIR_RECOMMENDATION_VALUES = {"Repair", "Replace", "Total Loss"}
INSPECTION_STATUS_VALUES = {"Assigned", "Scheduled", "In Progress", "Completed"}

_ALLOWED_VEHICLE_CONDITION = VEHICLE_CONDITION_VALUES | {PENDING}
_ALLOWED_DAMAGE_OBSERVED = DAMAGE_OBSERVED_VALUES | {PENDING}
_ALLOWED_DAMAGE_SEVERITY = DAMAGE_SEVERITY_VALUES | {PENDING}
_ALLOWED_REPAIR_RECOMMENDATION = REPAIR_RECOMMENDATION_VALUES | {PENDING}

# Real values observed in the approved dataset
# (ai_ml/datasets/CI_MICOP_15_Tables_Complete/08_vehicle_damage.xlsx, 654
# rows). A VehicleDamage row records a completed observation (unlike an
# in-progress inspection), so no "Pending" placeholder is offered here -
# every field must be a real value at creation time.
DAMAGE_TYPE_VALUES = {
    "Side Damage",
    "Rear Damage",
    "Multiple Damage",
    "Front Damage",
    "Glass Damage",
    "Engine Damage",
    "Total Loss",
}
DAMAGE_LOCATION_VALUES = {"Left", "Right", "Front", "Rear", "Multiple"}
REPAIR_OR_REPLACE_VALUES = {"Repair", "Replace"}


class VehicleDamageCreate(BaseModel):
    """Fields a Surveyor may submit to record a vehicle-damage
    observation. Neither Surveyor_ID nor Vehicle_ID is accepted here -
    the surveyor is resolved from the JWT and Vehicle_ID is always
    derived from the claim itself (see services/vehicle_damage_creation.py).
    """

    Claim_ID: str
    Damage_Type: str
    Damaged_Part: str = Field(min_length=1, max_length=50)
    Damage_Severity: str
    Damage_Location: str
    Estimated_Damage_Cost: Decimal = Field(ge=0)
    Repair_or_Replace: str
    Photo_Evidence_Available: bool = False
    Damage_Description: str = Field(min_length=1, max_length=1000)

    @field_validator("Damaged_Part", "Damage_Description")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field cannot be empty or whitespace-only")
        return stripped

    @field_validator("Damage_Type")
    @classmethod
    def _validate_damage_type(cls, value: str) -> str:
        if value not in DAMAGE_TYPE_VALUES:
            raise ValueError(f"Damage_Type must be one of {sorted(DAMAGE_TYPE_VALUES)}")
        return value

    @field_validator("Damage_Severity")
    @classmethod
    def _validate_damage_severity_real_only(cls, value: str) -> str:
        if value not in DAMAGE_SEVERITY_VALUES:
            raise ValueError(f"Damage_Severity must be one of {sorted(DAMAGE_SEVERITY_VALUES)}")
        return value

    @field_validator("Damage_Location")
    @classmethod
    def _validate_damage_location(cls, value: str) -> str:
        if value not in DAMAGE_LOCATION_VALUES:
            raise ValueError(f"Damage_Location must be one of {sorted(DAMAGE_LOCATION_VALUES)}")
        return value

    @field_validator("Repair_or_Replace")
    @classmethod
    def _validate_repair_or_replace(cls, value: str) -> str:
        if value not in REPAIR_OR_REPLACE_VALUES:
            raise ValueError(f"Repair_or_Replace must be one of {sorted(REPAIR_OR_REPLACE_VALUES)}")
        return value


class RepairEstimateCreate(BaseModel):
    """Fields a Surveyor may submit to record a repair estimate. Neither
    Surveyor_ID, Vehicle_ID, nor Customer_ID is accepted here -
    Vehicle_ID is always derived from the claim itself (see
    services/repair_estimate_creation.py). Garage_ID has no dedicated
    Garage table in the approved design, so it is recorded as a plain
    identifier string, not validated against a closed list.

    Actual_Repair_Days is optional: at estimate-creation time the repair
    has usually not happened yet, so a genuine value cannot be asserted.
    When omitted, it is stored as 0 - a value that never occurs in the
    approved dataset for a completed repair (real values start at 3) -
    documented as "not yet available", never a real zero-day repair.
    """

    Claim_ID: str
    Garage_ID: str = Field(min_length=1, max_length=30)
    Estimate_Date: date
    Repair_Estimate: Decimal = Field(ge=0)
    Repair_Cost: Decimal = Field(ge=0)
    Parts_Cost: Decimal = Field(ge=0)
    Labour_Cost: Decimal = Field(ge=0)
    Painting_Cost: Decimal = Field(ge=0)
    Replacement_Parts_Count: int = Field(ge=0)
    Repaired_Parts_Count: int = Field(ge=0)
    Estimated_Repair_Days: int = Field(ge=0)
    Actual_Repair_Days: int | None = Field(default=None, ge=0)

    @field_validator("Garage_ID")
    @classmethod
    def _reject_blank_garage_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Garage_ID cannot be empty or whitespace-only")
        return stripped


class SurveyorInspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Inspection_ID: str
    Claim_ID: str
    Surveyor_ID: str
    Inspection_Date: date
    Inspection_Location: str
    Vehicle_Condition: str
    Damage_Observed: str
    Damage_Severity: str
    Parts_Required: int
    Repair_Recommendation: str
    Surveyor_Comments: str
    Inspection_Status: str
    Survey_Report_Submitted: bool
    Surveyor_Confidence_Score: Decimal


class SurveyorInspectionCreate(BaseModel):
    """Fields a Surveyor may submit to start a new inspection.

    Surveyor_ID is deliberately absent - it always comes from the
    authenticated JWT (require_surveyor_employee_id), never from the
    request body, so a surveyor can never create an inspection under
    another surveyor's identity.
    """

    Claim_ID: str


class SurveyorInspectionUpdate(BaseModel):
    """Fields a surveyor may update after conducting an inspection.

    All optional - only the fields the surveyor supplies are changed.
    """

    Vehicle_Condition: str | None = None
    Damage_Observed: str | None = None
    Damage_Severity: str | None = None
    Parts_Required: int | None = Field(default=None, ge=0)
    Repair_Recommendation: str | None = None
    Surveyor_Comments: str | None = Field(default=None, max_length=2000)
    Inspection_Status: str | None = None
    Survey_Report_Submitted: bool | None = None
    Surveyor_Confidence_Score: Decimal | None = None

    @field_validator("Vehicle_Condition")
    @classmethod
    def _validate_vehicle_condition(cls, value: str | None) -> str | None:
        if value is not None and value not in _ALLOWED_VEHICLE_CONDITION:
            raise ValueError(f"Vehicle_Condition must be one of {sorted(_ALLOWED_VEHICLE_CONDITION)}")
        return value

    @field_validator("Damage_Observed")
    @classmethod
    def _validate_damage_observed(cls, value: str | None) -> str | None:
        if value is not None and value not in _ALLOWED_DAMAGE_OBSERVED:
            raise ValueError(f"Damage_Observed must be one of {sorted(_ALLOWED_DAMAGE_OBSERVED)}")
        return value

    @field_validator("Damage_Severity")
    @classmethod
    def _validate_damage_severity(cls, value: str | None) -> str | None:
        if value is not None and value not in _ALLOWED_DAMAGE_SEVERITY:
            raise ValueError(f"Damage_Severity must be one of {sorted(_ALLOWED_DAMAGE_SEVERITY)}")
        return value

    @field_validator("Repair_Recommendation")
    @classmethod
    def _validate_repair_recommendation(cls, value: str | None) -> str | None:
        if value is not None and value not in _ALLOWED_REPAIR_RECOMMENDATION:
            raise ValueError(f"Repair_Recommendation must be one of {sorted(_ALLOWED_REPAIR_RECOMMENDATION)}")
        return value

    @field_validator("Inspection_Status")
    @classmethod
    def _validate_inspection_status(cls, value: str | None) -> str | None:
        if value is not None and value not in INSPECTION_STATUS_VALUES:
            raise ValueError(f"Inspection_Status must be one of {sorted(INSPECTION_STATUS_VALUES)}")
        return value
