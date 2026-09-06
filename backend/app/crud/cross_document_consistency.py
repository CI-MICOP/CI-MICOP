from sqlalchemy.orm import Session

from app.db_models.cross_document_consistency import CrossDocumentConsistency


def list_by_claim(db: Session, claim_id: str) -> list[CrossDocumentConsistency]:
    return (
        db.query(CrossDocumentConsistency)
        .filter(CrossDocumentConsistency.Claim_ID == claim_id)
        .order_by(CrossDocumentConsistency.Consistency_ID)
        .all()
    )
