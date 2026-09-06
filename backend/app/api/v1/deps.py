"""Shared FastAPI dependencies for the v1 API: database session
injection, JWT-based current-user resolution, and role-based access
control (RBAC) helpers.
"""

from collections.abc import Generator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import authentication_user as crud_user
from app.db.session import SessionLocal
from app.db_models.authentication_user import AuthenticationUser

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> AuthenticationUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise credentials_error

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    user = crud_user.get_by_user_id(db, user_id)
    if user is None:
        raise credentials_error
    if user.Account_Status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    return user


def require_roles(*allowed_roles: str):
    """Dependency factory: raises 403 unless the current user's Role is
    one of allowed_roles."""

    def _check(current_user: AuthenticationUser = Depends(get_current_user)) -> AuthenticationUser:
        if current_user.Role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _check


def require_customer_id(current_user: AuthenticationUser = Depends(get_current_user)) -> str:
    """Resolves the Customer_ID for a Customer-role user, or 403."""
    if current_user.Role != "Customer" or not current_user.Customer_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only available to customer accounts",
        )
    return current_user.Customer_ID


def require_employee_id(current_user: AuthenticationUser = Depends(get_current_user)) -> str:
    """Resolves the Employee_ID for a Surveyor/Claims Officer user, or 403."""
    if current_user.Role not in ("Surveyor", "Claims Officer") or not current_user.Employee_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only available to staff accounts",
        )
    return current_user.Employee_ID
