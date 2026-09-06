from sqlalchemy import Boolean, Column, DateTime, Date, ForeignKey, Numeric, String, Text

from app.db.base_class import Base


class ClaimDecisionAudit(Base):
    """Append-only audit trail (Audit_Action includes Created/Updated/
    Verified/Closed), so Claim_ID is intentionally NOT unique - a claim
    can and should accumulate multiple audit rows over its lifecycle.

    Claims_Officer_ID references authentication_users.Employee_ID (same
    reasoning as SurveyorInspection.Surveyor_ID - see Step 2 report).
    Escalated_To ('MAN-xxxx' values) does not match any table in the
    15-table design and is stored as a plain identifier with no FK,
    per the approved schema (no Manager table).
    """

    __tablename__ = "claim_decision_audit"

    Audit_ID = Column(String(30), primary_key=True)
    Claim_ID = Column(String(30), ForeignKey("claims.Claim_ID"), nullable=False, index=True)
    Claims_Officer_ID = Column(
        String(30),
        ForeignKey("authentication_users.Employee_ID"),
        nullable=False,
        index=True,
    )
    AI_Recommendation = Column(String(30), nullable=False)
    AI_Confidence_Score = Column(Numeric(5, 4), nullable=False)
    Human_Review_Required = Column(Boolean, nullable=False)
    Final_Decision = Column(String(30), nullable=False)
    Decision_Reason = Column(Text, nullable=False)
    Approved_Amount = Column(Numeric(14, 2), nullable=False)
    Decision_Date = Column(Date, nullable=False)
    Escalation_Status = Column(String(30), nullable=False)
    Escalated_To = Column(String(30), nullable=True)
    Officer_Comments = Column(Text, nullable=False)
    Audit_Action = Column(String(30), nullable=False)
    Audit_Timestamp = Column(DateTime, nullable=False)
