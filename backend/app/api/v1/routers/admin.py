from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_roles
from app.crud import authentication_user as crud_user
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.user import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])

_admin_only = require_roles("Admin")


@router.get("/users", response_model=list[UserOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: AuthenticationUser = Depends(_admin_only),
    db: Session = Depends(get_db),
):
    return crud_user.list_all(db, skip, limit)


@router.get("/users/{user_id}", response_model=UserOut)
def read_user(
    user_id: str,
    current_user: AuthenticationUser = Depends(_admin_only),
    db: Session = Depends(get_db),
):
    user = crud_user.get_by_user_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
