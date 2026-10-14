from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header
from sqlalchemy import Connection, text

from ..core.errors import ApiError
from ..core.security import decode_token
from ..db.engine import get_conn

ROLES = ("OPERATOR", "QUALITY_ENGINEER", "QUALITY_MANAGER", "AUDITOR", "ADMIN")


@dataclass(frozen=True)
class CurrentUser:
    id: str
    employee_code: str
    full_name: str
    email: str
    role: str


def current_user(authorization: str | None = Header(default=None), conn: Connection = Depends(get_conn)) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHORIZED", "missing bearer token")
    try:
        claims = decode_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError as e:
        raise ApiError(401, "UNAUTHORIZED", f"invalid token: {e}") from e
    row = conn.execute(
        text("SELECT id::text, employee_code, full_name, email, role::text, is_active FROM users WHERE id = :id"),
        {"id": claims["sub"]},
    ).mappings().first()
    if not row or not row["is_active"]:
        raise ApiError(401, "UNAUTHORIZED", "user not found or inactive")
    return CurrentUser(row["id"], row["employee_code"], row["full_name"], row["email"], row["role"])


def require_roles(*roles: str) -> Callable[..., CurrentUser]:
    for r in roles:
        assert r in ROLES, r

    def dep(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles:
            raise ApiError(403, "FORBIDDEN", f"role {user.role} cannot perform this action (needs {', '.join(roles)})")
        return user

    return dep


ALL_ROLES = require_roles(*ROLES)
