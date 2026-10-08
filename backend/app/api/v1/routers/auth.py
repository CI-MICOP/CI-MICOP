from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.core.security import create_access_token, verify_password
from app.crud import authentication_user as crud_user
from app.db_models.authentication_user import AuthenticationUser
from app.schemas.token import Token
from app.schemas.user import UserOut
from app.services import login_throttle

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    throttle_key = login_throttle.make_key(form_data.username, request.client.host if request.client else None)
    wait_seconds = login_throttle.seconds_until_allowed(throttle_key)
    if wait_seconds:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(wait_seconds)},
        )

    user = crud_user.get_by_username(db, form_data.username)

    if user is None or not verify_password(form_data.password, user.Password_Hash):
        login_throttle.record_failure(throttle_key)
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

    login_throttle.record_success(throttle_key)
    user.Failed_Login_Count = 0
    user.Last_Login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    access_token = create_access_token(user_id=user.User_ID, role=user.Role)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: AuthenticationUser = Depends(get_current_user)):
    return current_user
