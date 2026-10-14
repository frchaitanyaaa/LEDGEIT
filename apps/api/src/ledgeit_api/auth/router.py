from __future__ import annotations

import base64

import jwt
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from ..core.errors import ApiError
from ..core.security import create_token, decode_token, hash_password, verify_password
from ..db.engine import get_conn
from .deps import ROLES, CurrentUser, current_user, require_roles

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class KeyIn(BaseModel):
    public_key: str = Field(description="Ed25519 public key, standard base64 (32 bytes)")
    label: str | None = None


class UserIn(BaseModel):
    employee_code: str
    full_name: str
    email: str
    password: str = Field(min_length=8)
    role: str


def _user_out(conn: Connection, user_id: str) -> dict:
    u = conn.execute(text(
        "SELECT id::text, employee_code, full_name, email, role::text AS role, is_active, created_at FROM users WHERE id=:id"
    ), {"id": user_id}).mappings().one()
    keys = conn.execute(text(
        "SELECT public_key, label, created_at FROM user_keys WHERE user_id=:id ORDER BY id"
    ), {"id": user_id}).mappings().all()
    return {**u, "public_keys": [dict(k) for k in keys], "public_key": keys[-1]["public_key"] if keys else None}


@router.post("/login")
def login(body: LoginIn, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        text("SELECT id::text, password_hash, role::text, is_active FROM users WHERE lower(email)=lower(:e)"),
        {"e": body.email},
    ).mappings().first()
    if not row or not row["is_active"] or not verify_password(body.password, row["password_hash"]):
        raise ApiError(401, "INVALID_CREDENTIALS", "invalid email or password")
    return {
        "access_token": create_token(row["id"], row["role"], "access"),
        "refresh_token": create_token(row["id"], row["role"], "refresh"),
        "token_type": "bearer",
        "user": _user_out(conn, row["id"]),
    }


@router.post("/refresh")
def refresh(body: RefreshIn, conn: Connection = Depends(get_conn)):
    try:
        claims = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError as e:
        raise ApiError(401, "UNAUTHORIZED", f"invalid refresh token: {e}") from e
    row = conn.execute(text("SELECT role::text, is_active FROM users WHERE id=:id"), {"id": claims["sub"]}).first()
    if not row or not row[1]:
        raise ApiError(401, "UNAUTHORIZED", "user inactive")
    return {"access_token": create_token(claims["sub"], row[0], "access"), "token_type": "bearer"}


@router.get("/me")
def me(user: CurrentUser = Depends(current_user), conn: Connection = Depends(get_conn)):
    return _user_out(conn, user.id)


@router.post("/keys", status_code=201)
def register_key(body: KeyIn, user: CurrentUser = Depends(current_user), conn: Connection = Depends(get_conn)):
    try:
        raw = base64.b64decode(body.public_key, validate=True)
    except ValueError as e:
        raise ApiError(422, "BAD_KEY", "public_key must be standard base64") from e
    if len(raw) != 32:
        raise ApiError(422, "BAD_KEY", "Ed25519 public key must be 32 bytes")
    conn.execute(text(
        "INSERT INTO user_keys(user_id, public_key, label) VALUES (:u, :k, :l) ON CONFLICT (user_id, public_key) DO NOTHING"
    ), {"u": user.id, "k": body.public_key, "l": body.label})
    return _user_out(conn, user.id)


users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("")
def list_users(_: CurrentUser = Depends(require_roles("ADMIN", "QUALITY_MANAGER", "AUDITOR")),
               conn: Connection = Depends(get_conn)):
    rows = conn.execute(text(
        "SELECT u.id::text, employee_code, full_name, email, role::text AS role, is_active, "
        "(SELECT count(*) FROM user_keys k WHERE k.user_id=u.id) AS key_count FROM users u ORDER BY employee_code"
    )).mappings().all()
    return [dict(r) for r in rows]


@users_router.post("", status_code=201)
def create_user(body: UserIn, _: CurrentUser = Depends(require_roles("ADMIN")), conn: Connection = Depends(get_conn)):
    if body.role not in ROLES:
        raise ApiError(422, "BAD_ROLE", f"role must be one of {ROLES}")
    exists = conn.execute(text("SELECT 1 FROM users WHERE employee_code=:c OR lower(email)=lower(:e)"),
                          {"c": body.employee_code, "e": body.email}).first()
    if exists:
        raise ApiError(409, "CONFLICT", "employee_code or email already exists")
    uid = conn.execute(text(
        "INSERT INTO users(employee_code, full_name, email, password_hash, role) "
        "VALUES (:c, :n, :e, :p, CAST(:r AS user_role)) RETURNING id::text"
    ), {"c": body.employee_code, "n": body.full_name, "e": body.email, "p": hash_password(body.password),
        "r": body.role}).scalar_one()
    return _user_out(conn, uid)
