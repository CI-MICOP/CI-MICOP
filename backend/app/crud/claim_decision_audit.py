from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.claim_decision_audit import ClaimDecisionAudit


def get(db: Session, audit_id: str) -> ClaimDecisionAudit | None:
    return db.query(ClaimDecisionAudit).filter(ClaimDecisionAudit.Audit_ID == audit_id).first()


def list_by_claim(db: Session, claim_id: str) -> list[ClaimDecisionAudit]:
    """Newest first - both existing consumers (DecisionPage's
    "latestAudit = audits[0]" and ClaimDetailsPage) already assume this
    order. Step 5.8.9 makes claim_decision_audit an append-only table in
    practice (previously every claim had at most one seeded row), so
    getting this order right now matters."""
    return (
        db.query(ClaimDecisionAudit)
        .filter(ClaimDecisionAudit.Claim_ID == claim_id)
        .order_by(ClaimDecisionAudit.Audit_Timestamp.desc())
        .all()
    )


def get_latest_by_claim(db: Session, claim_id: str) -> ClaimDecisionAudit | None:
    return (
        db.query(ClaimDecisionAudit)
        .filter(ClaimDecisionAudit.Claim_ID == claim_id)
        .order_by(ClaimDecisionAudit.Audit_Timestamp.desc())
        .first()
    )


def create(db: Session, audit: ClaimDecisionAudit) -> ClaimDecisionAudit:
    db.add(audit)
    return audit


def generate_audit_id(db: Session, attempts: int = 20) -> str:
    """AUD-YYYYMMDD-XXXXXX, same convention as Document_ID/Inspection_ID/
    Damage_ID/Evidence_ID/Estimate_ID, checked against the primary key
    before use - never accepted from the browser."""
    today = date.today().strftime("%Y%m%d")
    for _ in range(attempts):
        candidate = f"AUD-{today}-{uuid4().hex[:6].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Audit_ID")
