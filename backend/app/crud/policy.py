from sqlalchemy.orm import Session

from app.db_models.policy import Policy


def get(db: Session, policy_id: str) -> Policy | None:
    return db.query(Policy).filter(Policy.Policy_ID == policy_id).first()


def list_by_customer(db: Session, customer_id: str) -> list[Policy]:
    return db.query(Policy).filter(Policy.Customer_ID == customer_id).order_by(Policy.Policy_ID).all()
