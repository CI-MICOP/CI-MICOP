"""Schemas for Claims Officer / Admin actions that are not claim-child
read views (those live in schemas/claim_detail.py)."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SurveyorSummaryOut(BaseModel):
    """An eligible-for-assignment Surveyor account. AuthenticationUser has
    no Name field (unlike Customer.Customer_Name) - Username is the only
    real human-readable identifier available, so it is used as-is rather
    than fabricating a display name. Password_Hash and every other
    authentication-only field are deliberately excluded."""

    model_config = ConfigDict(from_attributes=True)

    Employee_ID: str
    Username: str
    Email: str
    Account_Status: str


class AssignSurveyorRequest(BaseModel):
    """Claims Officer/Admin request to assign a surveyor to a claim. Only
    the target surveyor's identifier is accepted - Claim_ID comes from the
    URL path (the claim already being worked on), and the resulting
    SurveyorInspection's own Inspection_ID/Claim_ID/Surveyor_ID are always
    derived server-side from authoritative records, never trusted from
    this body beyond the identifier itself being looked up and validated.
    """

    surveyor_employee_id: str = Field(min_length=1)


# Real values observed in the approved dataset
# (ai_ml/datasets/CI_MICOP_15_Tables_Complete/14_claim_decision_audit.xlsx,
# 654 rows) - the only three Final_Decision values that occur.
FINAL_DECISION_VALUES = {"Approved", "Rejected", "Partially Approved"}


class DecisionCreate(BaseModel):
    """Claims Officer's final decision on a claim.

    Deliberately excludes every AI-adjacent field (AI_Recommendation,
    AI_Confidence_Score, Human_Review_Required, Escalation_Status,
    Escalated_To) and every identity field (Claims_Officer_ID, Claim_ID) -
    those always come from the authenticated JWT, the URL path, or the
    latest genuinely-existing audit record (see
    services/claim_decision.py), never from the browser. This is the
    project's human-in-the-loop guarantee: nothing here lets a client
    submit a fabricated AI score alongside its own decision.
    """

    Final_Decision: str
    Decision_Reason: str = Field(min_length=1, max_length=2000)
    Approved_Amount: Decimal = Field(ge=0)
    Officer_Comments: str = Field(default="", max_length=2000)

    @field_validator("Decision_Reason")
    @classmethod
    def _reject_blank_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Decision_Reason cannot be empty or whitespace-only")
        return stripped

    @field_validator("Officer_Comments")
    @classmethod
    def _trim_comments(cls, value: str) -> str:
        return value.strip()

    @field_validator("Final_Decision")
    @classmethod
    def _validate_final_decision(cls, value: str) -> str:
        if value not in FINAL_DECISION_VALUES:
            raise ValueError(f"Final_Decision must be one of {sorted(FINAL_DECISION_VALUES)}")
        return value

    @model_validator(mode="after")
    def _validate_approved_amount_matches_decision(self) -> "DecisionCreate":
        # A Rejected claim must not disburse money. Note: the approved
        # dataset's own historical rows do NOT follow this rule (209
        # Rejected rows have positive Approved_Amount, up to 148,862) -
        # that data is treated as pre-existing noise, not a business rule
        # to preserve going forward, per this task's own instruction not
        # to invent unsupported rules while also asking this specific
        # rule to be enforced (see CLAIMS_OFFICER_DECISION_WORKFLOW.md).
        if self.Final_Decision == "Rejected" and self.Approved_Amount != 0:
            raise ValueError("A Rejected claim cannot have a positive Approved_Amount")

        # Approved / Partially Approved claims must actually approve some
        # amount - the real dataset never has Approved_Amount == 0 for
        # either of these two decision types.
        if self.Final_Decision in ("Approved", "Partially Approved") and self.Approved_Amount <= 0:
            raise ValueError(f"{self.Final_Decision} requires a positive Approved_Amount")

        return self
