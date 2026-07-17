"""
server-b-retrieval / auth_service.py

JWT-based authentication backed by MongoDB (collection: users).

Environment variables:
  JWT_SECRET  — signing key (change in production!)
  JWT_ALGO    — algorithm, default HS256
  JWT_TTL_DAYS — token lifetime in days, default 7
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from pymongo.errors import DuplicateKeyError

import company_service   # reuse _get_db() / index helpers

_SECRET    = os.environ.get("JWT_SECRET", "change-me-in-production-grand-pilot")
_ALGO      = os.environ.get("JWT_ALGO", "HS256")
_TTL_DAYS  = int(os.environ.get("JWT_TTL_DAYS", "7"))


# ── collection ────────────────────────────────────────────────────────────────

def _users():
    col = company_service._get_db()["users"]
    col.create_index("email", unique=True)
    return col


# ── password helpers ──────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=_TTL_DAYS)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def decode_token(token: str) -> Optional[str]:
    """Return email (sub) from token, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        return payload.get("sub")
    except JWTError:
        return None


# ── user CRUD ─────────────────────────────────────────────────────────────────

def register_user(email: str, password: str) -> str:
    """Create a new user and return a JWT token.

    Raises ValueError if the email is already registered.
    """
    hashed = _hash_password(password)
    now = datetime.now(timezone.utc)
    try:
        _users().insert_one({
            "email": email,
            "password_hash": hashed,
            "created_at": now,
        })
    except DuplicateKeyError:
        raise ValueError("Email đã được đăng ký.")
    return create_token(email)


def login_user(email: str, password: str) -> str:
    """Verify credentials and return a JWT token.

    Raises ValueError on bad email or wrong password.
    """
    user = _users().find_one({"email": email})
    if not user:
        raise ValueError("Email chưa được đăng ký.")
    if not _verify_password(password, user["password_hash"]):
        raise ValueError("Mật khẩu không đúng.")
    return create_token(email)
