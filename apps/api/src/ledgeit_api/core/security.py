from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings

ALGO = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, role: str, kind: str = "access") -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + (timedelta(minutes=s.jwt_access_minutes) if kind == "access" else timedelta(days=s.jwt_refresh_days))
    return jwt.encode({"sub": user_id, "role": role, "type": kind, "iat": now, "exp": exp}, s.jwt_secret, ALGO)


def decode_token(token: str, kind: str = "access") -> dict:
    claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGO])
    if claims.get("type") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return claims
