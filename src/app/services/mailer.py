"""Sends the confirmation code. Provider is chosen with RFP_MAIL_PROVIDER."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


class MailNotConfiguredError(AppError):
    status_code = 503
    code = "mail_not_configured"


class MailDeliveryError(AppError):
    status_code = 502
    code = "mail_delivery_failed"


def _compose(to: str, code: str) -> tuple[str, str, str]:
    minutes = get_settings().otp_ttl_s // 60
    subject = f"{code} is your Proposal Builder code"
    text = (
        f"Your confirmation code is {code}\n\n"
        f"It expires in {minutes} minutes. If you didn't try to sign up, you can ignore this email."
    )
    html = (
        '<div style="font-family:system-ui,sans-serif;max-width:420px">'
        "<p>Your confirmation code is</p>"
        f'<p style="font-size:32px;letter-spacing:8px;font-weight:600;margin:8px 0">{code}</p>'
        f"<p>It expires in {minutes} minutes. If you didn't try to sign up, you can ignore this email.</p></div>"
    )
    return subject, text, html


def send_code(to: str, code: str) -> None:
    settings = get_settings()
    provider = settings.mail_provider
    if provider == "log":
        if settings.environment == "production":
            raise MailNotConfiguredError("Email is not set up. Set RFP_MAIL_PROVIDER to smtp or resend.")
        logger.warning("CONFIRMATION CODE for %s: %s (RFP_MAIL_PROVIDER=log, local dev only)", to, code)
        return
    if not settings.mail_from:
        raise MailNotConfiguredError("Set RFP_MAIL_FROM to the address confirmation emails are sent from.")
    subject, text, html = _compose(to, code)
    try:
        if provider == "resend":
            if settings.resend_api_key is None:
                raise MailNotConfiguredError("Set RFP_RESEND_API_KEY.")
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}"},
                json={"from": settings.mail_from, "to": [to], "subject": subject, "text": text, "html": html},
                timeout=15,
            )
            resp.raise_for_status()
        else:
            if not settings.smtp_host:
                raise MailNotConfiguredError("Set RFP_SMTP_HOST (and RFP_SMTP_USER / RFP_SMTP_PASSWORD).")
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
                smtp.send_message(msg)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not send confirmation email to %s: %s", to, exc)
        raise MailDeliveryError("We couldn't send the confirmation email. Try again in a moment.") from exc
