from sqlalchemy.orm import Session

from app.db_models.claim_decision_audit import ClaimDecisionAudit


def list_by_claim(db: Session, claim_id: str) -> list[ClaimDecisionAudit]:
    return (
        db.query(ClaimDecisionAudit)
        .filter(ClaimDecisionAudit.Claim_ID == claim_id)
        .order_by(ClaimDecisionAudit.Audit_Timestamp)
        .all()
    )
