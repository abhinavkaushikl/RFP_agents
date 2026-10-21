"""Sign in with Google, with Google's servers faked."""
from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core import auth_crypto as ac
from test_auth import CREDS, _register, client  # noqa: F401  (fixtures and helpers)

PROFILE = {"sub": "google-sub-1", "email": "ada@example.com", "email_verified": True, "name": "Ada Lovelace"}


@pytest.fixture(autouse=True)
def _no_ip_throttle(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_AUTH_LOGIN_ATTEMPTS_PER_MINUTE", "0")
    get_settings.cache_clear()


@pytest.fixture
def google(client, monkeypatch):  # noqa: F811
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("RFP_GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("RFP_PUBLIC_URL", "https://app.example.com")
    get_settings.cache_clear()
    client.profile = dict(PROFILE)
    seen = {}

    def fake_fetch(*, code, verifier, redirect_uri):
        seen.update(code=code, verifier=verifier, redirect_uri=redirect_uri)
        return dict(client.profile)

    monkeypatch.setattr("app.api.routers.auth.google_oauth.fetch_profile", fake_fetch)
    client.seen = seen
    return client


def _begin(c, next_path=None):
    """Click 'Google': returns (state, redirect to Google). The browser keeps the oauth cookie."""
    resp = c.get("/api/auth/google/start" + (f"?next={next_path}" if next_path else ""), follow_redirects=False)
    assert resp.status_code == 302
    return parse_qs(urlparse(resp.headers["location"]).query)["state"][0], resp


def test_the_button_only_appears_when_google_is_configured(client):
    assert client.get("/api/auth/me").json()["google_enabled"] is False
    resp = client.get("/api/auth/google/start", follow_redirects=False)
    assert resp.status_code == 302 and "google_error=not_configured" in resp.headers["location"]


def test_start_sends_the_person_to_google_with_pkce_and_a_state(google):
    assert google.get("/api/auth/me").json()["google_enabled"] is True
    state, resp = _begin(google)
    url = urlparse(resp.headers["location"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert query["client_id"] == ["client-id.apps.googleusercontent.com"]
    assert query["redirect_uri"] == ["https://app.example.com/api/auth/google/callback"]
    assert query["code_challenge_method"] == ["S256"] and query["scope"] == ["openid email profile"]
    assert "httponly" in resp.headers["set-cookie"].lower() and "rfp_oauth" in resp.headers["set-cookie"]


def test_a_new_google_user_gets_an_account_and_is_signed_in(google):
    state, _ = _begin(google, "/solutions")
    resp = google.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "https://app.example.com/solutions"
    me = google.get("/api/auth/me").json()["user"]
    assert me["email"] == "ada@example.com" and me["name"] == "Ada Lovelace"
    assert google.get("/api/profiles").status_code == 200
    assert google.seen["redirect_uri"] == "https://app.example.com/api/auth/google/callback" and google.seen["verifier"]


def test_google_links_to_an_existing_password_account_with_the_same_email(google):
    from app.db.models import User

    _register(google)  # password account for ada@example.com
    google.post("/api/auth/logout")
    state, _ = _begin(google)
    google.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    db = google.Session()
    users = db.query(User).all()
    assert len(users) == 1 and users[0].google_sub == "google-sub-1"  # linked, not duplicated
    db.close()
    other = TestClient(google.app)
    assert other.post("/api/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]}).status_code == 200  # password still works


def test_a_tampered_or_missing_state_is_refused(google):
    _begin(google)
    resp = google.get("/api/auth/google/callback?code=abc&state=forged", follow_redirects=False)
    assert "google_error=expired" in resp.headers["location"] and google.get("/api/profiles").status_code == 401
    cold = TestClient(google.app)  # no oauth cookie at all
    assert "google_error=expired" in cold.get("/api/auth/google/callback?code=abc&state=x", follow_redirects=False).headers["location"]


def test_google_saying_no_or_an_unverified_email_signs_nobody_in(google):
    state, _ = _begin(google)
    denied = google.get(f"/api/auth/google/callback?error=access_denied&state={state}", follow_redirects=False)
    assert "google_error=cancelled" in denied.headers["location"]
    state, _ = _begin(google)
    google.profile["email_verified"] = False
    resp = google.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert "google_error=unverified_email" in resp.headers["location"] and google.get("/api/profiles").status_code == 401


def test_the_next_page_cannot_point_at_another_site(google):
    for evil in ("//evil.example.com", "https://evil.example.com", "/\\evil"):
        state, _ = _begin(google, evil)
        resp = google.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
        assert resp.headers["location"] == "https://app.example.com/"
        google.post("/api/auth/logout")


def test_signup_can_be_closed_to_new_google_users(google, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RFP_AUTH_ALLOW_SIGNUP", "false")
    get_settings.cache_clear()
    state, _ = _begin(google)
    resp = google.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert "google_error=signup_disabled" in resp.headers["location"]


def test_google_does_not_skip_the_authenticator(google):
    _register(google)
    setup = google.post("/api/auth/mfa/setup").json()
    google.post("/api/auth/mfa/enable", json={"code": ac.totp_code(setup["secret"], int(time.time() // 30))})
    google.post("/api/auth/logout")
    state, _ = _begin(google)
    resp = google.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    location = resp.headers["location"]
    assert location.startswith("https://app.example.com/login#mfa=") and "rfp_session" not in resp.headers.get("set-cookie", "")
    assert google.get("/api/profiles").status_code == 401
    token = parse_qs(urlparse(location).fragment)["mfa"][0]
    done = google.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": ac.totp_code(setup["secret"], int(time.time() // 30) + 1)})
    assert done.status_code == 200 and google.get("/api/profiles").status_code == 200
