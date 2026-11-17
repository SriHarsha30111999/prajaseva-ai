"""JWT authentication + role-based access control (RBAC).

DEMO IMPLEMENTATION:
Predefined demo users are used because original government
user accounts and authentication services are unavailable.
This authentication flow is intended only for assignment demonstration.
Replace with official identity integration in production.
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

# DEMO ONLY: a fixed fallback secret. Always set JWT_SECRET outside a demo.
SECRET_KEY = os.environ.get("JWT_SECRET", "prajaseva-demo-secret-change-me-0123456789")
ALGORITHM = "HS256"
TOKEN_HOURS = 8
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    expected = hash_password(password, bytes.fromhex(salt_hex)).split("$")[1]
    return hmac.compare_digest(expected, digest_hex)


def create_token(user: User) -> str:
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    try:
        data = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.query(User).filter(User.username == data.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user


def require_roles(*roles: str):
    """FastAPI dependency: only the listed roles may call the endpoint."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Role {user.role} is not permitted to perform this action")
        return user

    return checker
