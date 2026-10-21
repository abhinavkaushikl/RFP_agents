"""Authenticator-app two-step sign-in."""
from __future__ import annotations

import base64
import time

import pytest
from fastapi.testclient import TestClient

from app.core import auth_crypto as ac
from test_auth import CREDS, _register, client  # noqa: F401  (fixtures and helpers)


@pytest.fixture(autouse=True)
def _no_ip_throttle(monkeypatch):
    """These tests make many sign-in calls from one address; the per-IP limit has its own test."""
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_AUTH_LOGIN_ATTEMPTS_PER_MINUTE", "0")
    get_settings.cache_clear()


# ── the algorithm itself ───────────────────────────────────────────────
def test_totp_matches_the_rfc_6238_test_vectors():
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")  # the RFC's SHA-1 test key
    assert ac.totp_code(secret, 59 // 30) == "287082"
    assert ac.totp_code(secret, 1111111109 // 30) == "081804"
    assert ac.totp_code(secret, 1234567890 // 30) == "005924"


def test_verify_allows_one_step_of_drift_but_never_reuse():
    secret = ac.new_totp_secret()
    now = 1_700_000_000
    step = now // 30
    assert ac.verify_totp(secret, ac.totp_code(secret, step), now=now) == step
    assert ac.verify_totp(secret, ac.totp_code(secret, step - 1), now=now) == step - 1
    assert ac.verify_totp(secret, ac.totp_code(secret, step + 1), now=now) == step + 1
    assert ac.verify_totp(secret, ac.totp_code(secret, step - 3), now=now) is None  # too old
    assert ac.verify_totp(secret, ac.totp_code(secret, step), now=now, last_step=step) is None  # already used
    assert ac.verify_totp(secret, "12345", now=now) is None and ac.verify_totp(secret, "abcdef", now=now) is None


def test_sealed_secrets_round_trip_and_reject_tampering():
    sealed = ac.seal("JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in sealed
    assert ac.unseal(sealed) == "JBSWY3DPEHPK3PXP"
    assert ac.seal("JBSWY3DPEHPK3PXP") != sealed  # fresh nonce every time
    assert ac.unseal(sealed[:-3] + "AAA") is None and ac.unseal("garbage") is None and ac.unseal(None) is None


def test_the_login_token_cannot_be_used_as_a_session_and_vice_versa():
    uid = "5f0c1c0a-6a9d-4d9b-8b6a-0b3f5a3c9d11"
    mfa = ac.issue_mfa_token(uid)
    assert ac.read_mfa_token(mfa) == uid
    assert ac.read_session(mfa) is None  # a stolen "password ok" token is not a login
    assert ac.read_mfa_token(ac.issue_session(uid)) is None
    assert ac.read_mfa_token(mfa, now=time.time() + 400) is None  # expires after 5 minutes


# ── the flows ──────────────────────────────────────────────────────────
def _enrol(client):
    """Register, then turn two-step on. Returns (secret, backup_codes)."""
    assert _register(client).status_code == 200
    setup = client.post("/api/auth/mfa/setup").json()
    assert setup["qr"].startswith("data:image/svg+xml;base64,") and setup["otpauth_uri"].startswith("otpauth://totp/")
    code = ac.totp_code(setup["secret"], int(time.time() // 30))
    enabled = client.post("/api/auth/mfa/enable", json={"code": code})
    assert enabled.status_code == 200, enabled.text
    return setup["secret"], enabled.json()["backup_codes"]


def _password_step(client):
    other = TestClient(client.app)
    resp = other.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]})
    return other, resp


def test_setup_needs_a_confirmed_code_and_stores_the_secret_sealed(client):
    from app.db.models import User

    _register(client)
    setup = client.post("/api/auth/mfa/setup").json()
    db = client.Session()
    stored = db.query(User).one()
    assert stored.totp_enabled_at is None and setup["secret"] not in (stored.totp_secret_enc or "")
    db.close()
    assert client.post("/api/auth/mfa/enable", json={"code": "000000"}).status_code == 401
    assert client.get("/api/auth/me").json()["user"]["mfa_enabled"] is False


def test_signing_in_needs_the_authenticator_code_after_the_password(client):
    secret, _ = _enrol(client)
    assert client.get("/api/auth/me").json()["user"]["mfa_enabled"] is True

    other, step1 = _password_step(client)
    body = step1.json()
    assert step1.status_code == 200 and body["mfa_required"] is True and "set-cookie" not in step1.headers
    assert other.get("/api/profiles").status_code == 401  # password alone is not enough

    code = ac.totp_code(secret, int(time.time() // 30) + 1)  # next step: unused, within drift
    done = other.post("/api/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": code})
    assert done.status_code == 200 and done.json()["user"]["email"] == "ada@example.com"
    assert other.get("/api/profiles").status_code == 200


def test_a_used_code_cannot_be_replayed_and_wrong_codes_lock_the_account_briefly(client):
    secret, _ = _enrol(client)
    other, step1 = _password_step(client)
    token = step1.json()["mfa_token"]
    code = ac.totp_code(secret, int(time.time() // 30) + 1)
    assert other.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": code}).status_code == 200

    again, step1b = _password_step(client)
    token2 = step1b.json()["mfa_token"]
    assert again.post("/api/auth/mfa/verify", json={"mfa_token": token2, "code": code}).status_code == 401  # replay
    for _ in range(4):
        assert again.post("/api/auth/mfa/verify", json={"mfa_token": token2, "code": "000000"}).status_code == 401
    # Five misses in all: now even the right code is refused for a few minutes.
    good = ac.totp_code(secret, int(time.time() // 30) - 1)
    assert again.post("/api/auth/mfa/verify", json={"mfa_token": token2, "code": good}).status_code == 429


def test_backup_codes_work_once(client):
    _, backups = _enrol(client)
    assert len(backups) == 8
    other, step1 = _password_step(client)
    token = step1.json()["mfa_token"]
    assert other.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": backups[0]}).status_code == 200
    again, step1b = _password_step(client)
    assert again.post("/api/auth/mfa/verify", json={"mfa_token": step1b.json()["mfa_token"], "code": backups[0]}).status_code == 401
    assert again.post("/api/auth/mfa/verify", json={"mfa_token": step1b.json()["mfa_token"], "code": backups[1].upper()}).status_code == 200


def test_a_session_cookie_forged_from_the_login_token_does_not_work(client):
    _enrol(client)
    other, step1 = _password_step(client)
    other.cookies.set("rfp_session", step1.json()["mfa_token"])
    assert other.get("/api/profiles").status_code == 401


def test_turning_it_off_needs_the_password_and_a_code(client):
    secret, backups = _enrol(client)
    code = ac.totp_code(secret, int(time.time() // 30) + 1)
    assert client.post("/api/auth/mfa/disable", json={"password": "wrong", "code": code}).status_code == 401
    assert client.post("/api/auth/mfa/disable", json={"password": CREDS["password"], "code": "000000"}).status_code == 401
    assert client.post("/api/auth/mfa/disable", json={"password": CREDS["password"], "code": backups[0]}).status_code == 200
    assert client.get("/api/auth/me").json()["user"]["mfa_enabled"] is False
    other, step1 = _password_step(client)
    assert "user" in step1.json()  # back to password-only sign-in


def test_resetting_the_password_by_email_does_not_skip_the_authenticator(client):
    _enrol(client)
    client.post("/api/auth/logout")
    client.post("/api/auth/forgot", json={"email": CREDS["email"]})
    email, code = client.sent[-1]
    resp = client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": "a brand new pass"})
    assert resp.status_code == 200 and resp.json() == {"password_updated": True, "login_required": True}
    assert "set-cookie" not in resp.headers and client.get("/api/profiles").status_code == 401
    other = TestClient(client.app)
    assert other.post("/api/auth/login", json={"email": email, "password": "a brand new pass"}).json()["mfa_required"] is True


def test_setup_requires_being_signed_in(client):
    assert client.post("/api/auth/mfa/setup").status_code == 401
    assert client.post("/api/auth/mfa/enable", json={"code": "123456"}).status_code == 401
