from sqlalchemy.orm import Session

from app.db_models.authentication_user import AuthenticationUser


def get_by_username(db: Session, username: str) -> AuthenticationUser | None:
    return db.query(AuthenticationUser).filter(AuthenticationUser.Username == username).first()


def get_by_user_id(db: Session, user_id: str) -> AuthenticationUser | None:
    return db.query(AuthenticationUser).filter(AuthenticationUser.User_ID == user_id).first()


def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[AuthenticationUser]:
    return db.query(AuthenticationUser).order_by(AuthenticationUser.User_ID).offset(skip).limit(limit).all()


def get_by_employee_id(db: Session, employee_id: str) -> AuthenticationUser | None:
    return db.query(AuthenticationUser).filter(AuthenticationUser.Employee_ID == employee_id).first()


def list_active_surveyors(db: Session) -> list[AuthenticationUser]:
    """Surveyor accounts eligible to be assigned to a claim: Role="Surveyor"
    and Account_Status="Active" - the same "Active" convention already used
    to gate login (see api/v1/deps.py::get_current_user)."""
    return (
        db.query(AuthenticationUser)
        .filter(AuthenticationUser.Role == "Surveyor", AuthenticationUser.Account_Status == "Active")
        .order_by(AuthenticationUser.Employee_ID)
        .all()
    )
