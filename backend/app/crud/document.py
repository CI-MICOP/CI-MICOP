from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db_models.document import Document


def get(db: Session, document_id: str) -> Document | None:
    return db.query(Document).filter(Document.Document_ID == document_id).first()


def list_by_claim(db: Session, claim_id: str) -> list[Document]:
    return db.query(Document).filter(Document.Claim_ID == claim_id).order_by(Document.Document_ID).all()


def create(db: Session, document: Document) -> Document:
    db.add(document)
    return document


def generate_document_id(db: Session, attempts: int = 20) -> str:
    """DOC-YYYYMMDD-XXXXXX, checked against the primary key before use -
    never accepted from the browser."""
    today = date.today().strftime("%Y%m%d")
    for _ in range(attempts):
        candidate = f"DOC-{today}-{uuid4().hex[:6].upper()}"
        if get(db, candidate) is None:
            return candidate
    raise RuntimeError("Could not generate a unique Document_ID")
