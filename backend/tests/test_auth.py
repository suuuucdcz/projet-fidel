"""Auth tests — runnable without a database or network.

Run from the backend/ directory:  python -m pytest tests/
"""
import os

# Must be set before importing auth (it reads SESSION_SECRET at import time).
os.environ.setdefault("SESSION_SECRET", "test-secret")

# Run these tests without a real database: force the Supabase env empty so db.py
# leaves the client as None (load_dotenv won't override already-set vars). The auth
# checks we test here run *before* any DB access anyway.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth import create_merchant_token, get_current_merchant_id
from main import app

client = TestClient(app)


def test_token_roundtrip():
    token = create_merchant_token("merchant-123")
    assert get_current_merchant_id(f"Bearer {token}") == "merchant-123"


def test_invalid_token_rejected():
    with pytest.raises(HTTPException) as exc:
        get_current_merchant_id("Bearer not-a-real-token")
    assert exc.value.status_code == 401


def test_missing_header_rejected():
    with pytest.raises(HTTPException) as exc:
        get_current_merchant_id(None)
    assert exc.value.status_code == 401


def test_scan_requires_auth():
    # No Authorization header -> 401, before any DB access.
    res = client.post("/cards/scan", json={"customer_id": "abc"})
    assert res.status_code == 401


def test_push_requires_auth():
    res = client.post("/marketing/push", json={"header": "h", "body": "b"})
    assert res.status_code == 401


def test_merchant_settings_requires_auth():
    res = client.post("/merchants/settings", json={"reward_threshold": 5, "reward_description": "x"})
    assert res.status_code == 401


def test_login_is_rate_limited():
    # The login endpoint is limited to 10/minute per IP; the 11th call is rejected.
    payload = {"email": "x@y.z", "password": "nope"}
    for _ in range(10):
        client.post("/merchants/login", json=payload)
    res = client.post("/merchants/login", json=payload)
    assert res.status_code == 429
