from __future__ import annotations

from fastapi.testclient import TestClient

from test_auth import CREDS, _register, client  # noqa: F401  (fixtures and helpers)


def _forgot(client, email=CREDS["email"]):
    assert client.post("/api/auth/forgot", json={"email": email}).json() == {"ok": True}


def test_reset_password_with_the_emailed_code(client):
    _register(client)
    client.post("/api/auth/logout")
    _forgot(client)
    email, code = client.sent[-1]
    assert email == "ada@example.com"

    resp = client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": "a brand new pass"})
    assert resp.status_code == 200 and resp.json()["user"]["email"] == "ada@example.com"
    assert client.get("/api/profiles").status_code == 200  # signed in by the reset

    other = TestClient(client.app)
    assert other.post("/api/auth/login", json={"email": email, "password": CREDS["password"]}).status_code == 401
    assert other.post("/api/auth/login", json={"email": email, "password": "a brand new pass"}).status_code == 200


def test_reset_code_is_single_use_and_wrong_codes_fail(client):
    _register(client)
    _forgot(client)
    email, code = client.sent[-1]
    bad = "000000" if code != "000000" else "111111"
    assert client.post("/api/auth/reset-password", json={"email": email, "code": bad, "new_password": "long enough pw"}).status_code == 401
    assert client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": "long enough pw"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": "another long pw"}).status_code == 401


def test_new_password_must_be_long_enough(client):
    _register(client)
    _forgot(client)
    email, code = client.sent[-1]
    assert client.post("/api/auth/reset-password", json={"email": email, "code": code, "new_password": "short"}).status_code == 422


def test_forgot_does_not_reveal_which_addresses_have_accounts(client):
    sent_before = len(client.sent)
    _forgot(client, "nobody@example.com")
    assert len(client.sent) == sent_before  # same answer, no email


def test_forgot_still_answers_ok_when_the_email_cannot_be_sent(client, monkeypatch):
    from app.services.mailer import MailDeliveryError

    _register(client)

    def broken(to, code):
        raise MailDeliveryError("smtp down")

    monkeypatch.setattr("app.api.routers.auth.send_code", broken)
    _forgot(client)
