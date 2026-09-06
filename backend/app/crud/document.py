from sqlalchemy.orm import Session

from app.db_models.document import Document


def get(db: Session, document_id: str) -> Document | None:
    return db.query(Document).filter(Document.Document_ID == document_id).first()


def list_by_claim(db: Session, claim_id: str) -> list[Document]:
    return db.query(Document).filter(Document.Claim_ID == claim_id).order_by(Document.Document_ID).all()
