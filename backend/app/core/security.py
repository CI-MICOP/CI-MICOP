"""Password hashing and JWT access tokens.

Uses bcrypt directly (no passlib) for hashing, and PyJWT for tokens.
JWT_SECRET_KEY / JWT_ALGORITHM / ACCESS_TOKEN_EXPIRE_MINUTES come from
app.core.config (backend/.env) - never hard-coded.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (e.g. a placeholder value that was never bcrypt-hashed).
        return False


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on any invalid/expired token.

    Step 5.8.26: `exp` and `sub` must be present. PyJWT only checks `exp`
    when it exists, so without this a correctly signed token with no expiry
    would be valid forever."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
