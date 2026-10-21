from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import auth_crypto


@pytest.fixture
def client(monkeypatch, sent_codes):
    from app.api.deps import get_db
    from app.bootstrap import create_app
    from app.core.config import get_settings
    from app.db.models import EmailOtp, User

    monkeypatch.setenv("RFP_AUTH_REQUIRED", "true")
    monkeypatch.setenv("RFP_AUTH_SECRET", "test-secret")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    User.__table__.create(engine)
    EmailOtp.__table__.create(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override
    c = TestClient(app)
    c.Session = Session
    c.sent = sent_codes
    return c


CREDS = {"email": "Ada@Example.com", "password": "correct horse", "name": "Ada"}


def _register(client, creds=CREDS):
    """Sign up and confirm with the emailed code; leaves the client signed in."""
    assert client.post("/api/auth/signup", json=creds).json()["verification_required"] is True
    email, code = client.sent[-1]
    return client.post("/api/auth/verify", json={"email": email, "code": code})


def test_password_hash_roundtrip():
    stored = auth_crypto.hash_password("hunter2hunter2")
    assert auth_crypto.verify_password("hunter2hunter2", stored)
    assert not auth_crypto.verify_password("nope", stored)
    assert not auth_crypto.verify_password("x", "garbage")


def test_session_token_rejects_tampering_and_expiry():
    uid = "5f0c1c0a-6a9d-4d9b-8b6a-0b3f5a3c9d11"
    token = auth_crypto.issue_session(uid, now=1_000)
    assert auth_crypto.read_session(token, now=1_001) == uid
    assert auth_crypto.read_session(token, now=1_000 + 8 * 24 * 3600) is None
    assert auth_crypto.read_session(token[:-2] + "xx", now=1_001) is None
    assert auth_crypto.read_session(None) is None


def test_api_requires_sign_in(client):
    assert client.get("/api/profiles").status_code == 401
    assert client.get("/api/auth/me").json() == {"user": None, "auth_required": True, "signup_enabled": True}


def test_signup_needs_the_emailed_code_before_anyone_is_signed_in(client):
    resp = client.post("/api/auth/signup", json=CREDS)
    assert resp.status_code == 200 and resp.json() == {"verification_required": True, "email": "ada@example.com"}
    assert "set-cookie" not in resp.headers
    assert client.get("/api/profiles").status_code == 401
    email, code = client.sent[-1]
    assert email == "ada@example.com" and len(code) == 6 and code.isdigit()

    ok = client.post("/api/auth/verify", json={"email": "ada@example.com", "code": code})
    assert ok.status_code == 200 and ok.json()["user"]["name"] == "Ada"
    assert "httponly" in ok.headers["set-cookie"].lower()
    assert client.get("/api/profiles").status_code == 200


def test_code_is_stored_hashed_and_single_use(client):
    from app.db.models import EmailOtp

    client.post("/api/auth/signup", json=CREDS)
    _, code = client.sent[-1]
    db = client.Session()
    assert code not in db.query(EmailOtp).one().code_hash
    db.close()
    assert client.post("/api/auth/verify", json={"email": CREDS["email"], "code": code}).status_code == 200
    assert client.post("/api/auth/verify", json={"email": CREDS["email"], "code": code}).status_code == 401


def test_wrong_code_is_rejected_and_attempts_are_limited(client):
    client.post("/api/auth/signup", json=CREDS)
    _, code = client.sent[-1]
    bad = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert client.post("/api/auth/verify", json={"email": CREDS["email"], "code": bad}).status_code == 401
    # After five misses even the right code stops working until a new one is requested.
    assert client.post("/api/auth/verify", json={"email": CREDS["email"], "code": code}).status_code == 429
    client.post("/api/auth/resend", json={"email": CREDS["email"]})
    _, fresh = client.sent[-1]
    assert client.post("/api/auth/verify", json={"email": CREDS["email"], "code": fresh}).status_code == 200


def test_expired_code_is_rejected(client):
    from app.db.models import EmailOtp

    client.post("/api/auth/signup", json=CREDS)
    _, code = client.sent[-1]
    db = client.Session()
    otp = db.query(EmailOtp).one()
    otp.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    db.commit()
    db.close()
    resp = client.post("/api/auth/verify", json={"email": CREDS["email"], "code": code})
    assert resp.status_code == 401 and "expired" in resp.json()["error"]["message"]


def test_unconfirmed_login_sends_a_new_code_instead_of_signing_in(client):
    client.post("/api/auth/signup", json=CREDS)
    sent_before = len(client.sent)
    resp = client.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]})
    assert resp.json() == {"verification_required": True, "email": "ada@example.com"}
    assert len(client.sent) == sent_before + 1
    assert client.get("/api/profiles").status_code == 401


def test_nobody_can_squat_an_address_they_have_not_confirmed(client):
    client.post("/api/auth/signup", json={**CREDS, "password": "squatter password"})
    # The real owner signs up later with the same address and takes it over.
    assert _register(client).status_code == 200
    other = TestClient(client.app)
    assert other.post("/api/auth/login", json={"email": CREDS["email"], "password": "squatter password"}).status_code == 401
    assert other.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}).status_code == 200


def test_confirmed_addresses_cannot_be_signed_up_again(client):
    _register(client)
    assert TestClient(client.app).post("/api/auth/signup", json=CREDS).status_code == 409


def test_resend_cooldown_and_no_email_probing(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_OTP_RESEND_COOLDOWN_S", "60")
    get_settings.cache_clear()
    client.post("/api/auth/signup", json=CREDS)
    assert client.post("/api/auth/resend", json={"email": CREDS["email"]}).status_code == 429
    # An address with no account gets the same "ok", and no email is sent.
    sent_before = len(client.sent)
    assert client.post("/api/auth/resend", json={"email": "nobody@example.com"}).json() == {"ok": True}
    assert len(client.sent) == sent_before


def test_login_logout_flow(client):
    _register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/profiles").status_code == 401
    assert client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong"}).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "ADA@example.com", "password": CREDS["password"]})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "ada@example.com"
    assert client.get("/api/profiles").status_code == 200


def test_signup_validation(client):
    assert client.post("/api/auth/signup", json={**CREDS, "email": "nope"}).status_code == 422
    assert client.post("/api/auth/signup", json={**CREDS, "password": "short"}).status_code == 422


def test_login_is_throttled(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_AUTH_LOGIN_ATTEMPTS_PER_MINUTE", "3")
    get_settings.cache_clear()
    codes = [client.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401]
    assert 429 in codes[3:]


def test_signup_can_be_disabled(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_AUTH_ALLOW_SIGNUP", "false")
    get_settings.cache_clear()
    assert client.post("/api/auth/signup", json=CREDS).status_code == 401


def test_unauthenticated_error_code_lets_the_web_app_redirect(client):
    assert client.get("/api/profiles").json()["error"]["code"] == "auth_required"


def test_production_refuses_to_log_codes():
    from app.core.config import get_settings
    from app.services.mailer import MailNotConfiguredError, send_code

    import os
    os.environ["RFP_ENVIRONMENT"] = "production"
    get_settings.cache_clear()
    try:
        with pytest.raises(MailNotConfiguredError):
            send_code("a@b.co", "123456")
    finally:
        del os.environ["RFP_ENVIRONMENT"]
        get_settings.cache_clear()


def test_failed_send_does_not_trigger_the_resend_cooldown(client, monkeypatch):
    from app.core.config import get_settings
    from app.services.mailer import MailDeliveryError

    monkeypatch.setenv("RFP_OTP_RESEND_COOLDOWN_S", "60")
    get_settings.cache_clear()
    calls = {"n": 0}

    def flaky(to, code):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MailDeliveryError("smtp down")
        client.sent.append((to, code))

    monkeypatch.setattr("app.api.routers.auth.send_code", flaky)
    assert client.post("/api/auth/signup", json=CREDS).status_code == 502
    assert client.post("/api/auth/signup", json=CREDS).status_code == 200  # not 429
