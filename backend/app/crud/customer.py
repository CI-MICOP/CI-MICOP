from sqlalchemy.orm import Session

from app.db_models.customer import Customer


def get(db: Session, customer_id: str) -> Customer | None:
    return db.query(Customer).filter(Customer.Customer_ID == customer_id).first()
