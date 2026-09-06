from sqlalchemy.orm import Session

from app.db_models.authentication_user import AuthenticationUser


def get_by_username(db: Session, username: str) -> AuthenticationUser | None:
    return db.query(AuthenticationUser).filter(AuthenticationUser.Username == username).first()


def get_by_user_id(db: Session, user_id: str) -> AuthenticationUser | None:
    return db.query(AuthenticationUser).filter(AuthenticationUser.User_ID == user_id).first()


def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[AuthenticationUser]:
    return db.query(AuthenticationUser).order_by(AuthenticationUser.User_ID).offset(skip).limit(limit).all()
