from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.core.security import create_access_token, verify_password
from app.crud import authentication_user as crud_user
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.token import Token
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud_user.get_by_username(db, form_data.username)

    if user is None or not verify_password(form_data.password, user.Password_Hash):
        if user is not None:
            user.Failed_Login_Count = (user.Failed_Login_Count or 0) + 1
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.Account_Status != "Active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    user.Failed_Login_Count = 0
    user.Last_Login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    access_token = create_access_token(user_id=user.User_ID, role=user.Role)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: AuthenticationUser = Depends(get_current_user)):
    return current_user
