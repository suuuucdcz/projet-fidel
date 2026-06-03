"""Merchant session authentication.

A signed JWT is issued at merchant login and sent back by the scanner app as
``Authorization: Bearer <token>``. Protected endpoints derive the merchant id from
the verified token (never from the request body), so a merchant can only act on its
own account.
"""
import os
import secrets
import time

import jwt
from fastapi import Header, HTTPException

_ALGORITHM = "HS256"

# Stable signing secret. In production SESSION_SECRET MUST be set (and kept stable),
# otherwise every restart invalidates all existing tokens. We fall back to a random
# per-process secret in dev, with a loud warning.
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    print("WARNING: SESSION_SECRET not set — using a random per-process secret. "
          "Merchant sessions will be invalidated on restart. Set SESSION_SECRET in production.")

# Session lifetime in days (default: 30 — counter-tablet convenience).
try:
    SESSION_TOKEN_DAYS = int(os.environ.get("SESSION_TOKEN_DAYS", "30"))
except ValueError:
    SESSION_TOKEN_DAYS = 30


def create_merchant_token(merchant_id: str) -> str:
    """Create a signed session token for a merchant."""
    now = int(time.time())
    payload = {
        "sub": str(merchant_id),
        "iat": now,
        "exp": now + SESSION_TOKEN_DAYS * 24 * 3600,
    }
    return jwt.encode(payload, SESSION_SECRET, algorithm=_ALGORITHM)


def get_current_merchant_id(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: validate the Bearer token and return its merchant id.

    Raises 401 if the token is missing, malformed, expired, or has a bad signature.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentification requise")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée, reconnectez-vous")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Jeton de session invalide")

    merchant_id = payload.get("sub")
    if not merchant_id:
        raise HTTPException(status_code=401, detail="Jeton de session invalide")
    return merchant_id
