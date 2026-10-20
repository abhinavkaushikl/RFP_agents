from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import auth_crypto


@pytest.fixture
def client(monkeypatch):
    from app.api.deps import get_db
    from app.bootstrap import create_app
    from app.core.config import get_settings
    from app.db.models import User

    monkeypatch.setenv("RFP_AUTH_REQUIRED", "true")
    monkeypatch.setenv("RFP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    User.__table__.create(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override
    return TestClient(app)


CREDS = {"email": "Ada@Example.com", "password": "correct horse", "name": "Ada"}


def test_password_hash_roundtrip():
    stored = auth_crypto.hash_password("hunter2hunter2")
    assert auth_crypto.verify_password("hunter2hunter2", stored)
    assert not auth_crypto.verify_password("nope", stored)
    assert not auth_crypto.verify_password("x", "garbage")


def test_session_token_rejects_tampering_and_expiry():
    token = auth_crypto.issue_session("abc", now=1_000)
    assert auth_crypto.read_session(token, now=1_001) == "abc"
    assert auth_crypto.read_session(token, now=1_000 + 8 * 24 * 3600) is None
    assert auth_crypto.read_session(token[:-2] + "xx", now=1_001) is None
    assert auth_crypto.read_session(None) is None


def test_api_requires_sign_in(client):
    assert client.get("/api/profiles").status_code == 401
    body = client.get("/api/auth/me").json()
    assert body == {"user": None, "auth_required": True, "signup_enabled": True}


def test_signup_login_logout_flow(client):
    resp = client.post("/api/auth/signup", json=CREDS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == "ada@example.com"
    assert "httponly" in resp.headers["set-cookie"].lower()

    assert client.get("/api/auth/me").json()["user"]["name"] == "Ada"
    assert client.get("/api/profiles").status_code == 200

    client.post("/api/auth/logout")
    assert client.get("/api/profiles").status_code == 401

    assert client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong"}).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "ADA@example.com", "password": CREDS["password"]})
    assert ok.status_code == 200
    assert client.get("/api/profiles").status_code == 200


def test_signup_validation(client):
    assert client.post("/api/auth/signup", json={**CREDS, "email": "nope"}).status_code == 422
    assert client.post("/api/auth/signup", json={**CREDS, "password": "short"}).status_code == 422
    assert client.post("/api/auth/signup", json=CREDS).status_code == 200
    assert client.post("/api/auth/signup", json=CREDS).status_code == 409


def test_login_is_throttled(client, monkeypatch):
    monkeypatch.setenv("RFP_AUTH_LOGIN_ATTEMPTS_PER_MINUTE", "3")
    from app.core.config import get_settings

    get_settings.cache_clear()
    codes = [client.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401]
    assert 429 in codes[3:]


def test_signup_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("RFP_AUTH_ALLOW_SIGNUP", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert client.post("/api/auth/signup", json=CREDS).status_code == 401


def test_unauthenticated_error_code_lets_the_web_app_redirect(client):
    assert client.get("/api/profiles").json()["error"]["code"] == "auth_required"
