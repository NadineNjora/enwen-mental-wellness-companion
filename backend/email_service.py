"""Brevo own-mailbox connection test. Never sends invitations or safety alerts.

This module is deliberately not imported by registration, chat or the local
Mailpit workflow. Enabling a connection test cannot redirect existing test mail.
"""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email

load_dotenv(Path(__file__).with_name(".env"))
TEST_SUBJECT = "ENWEN email connection test"
TEST_BODY = "This is your requested ENWEN email connection test. It is not a safety alert and contains no student records or invitation links."


class EmailServiceError(RuntimeError):
    pass


def validate_configuration():
    if os.getenv("EMAIL_MODE", "disabled").strip().lower() != "live" or os.getenv("LIVE_EMAIL_ENABLED", "false").strip().lower() != "true":
        raise EmailServiceError("Live email is disabled. Enable it only when ready for a deliberate own-mailbox connection test.")
    if os.getenv("EMAIL_PROVIDER", "brevo").strip().lower() != "brevo":
        raise EmailServiceError("Only EMAIL_PROVIDER=brevo is configured. No provider fallback is attempted.")
    key = os.getenv("BREVO_API_KEY", "").strip()
    if not key:
        raise EmailServiceError("Set BREVO_API_KEY privately in backend/.env.")
    if os.getenv("EMAIL_SENDER_VERIFIED", "false").strip().lower() != "true":
        raise EmailServiceError("Verify your sender and transactional email access in Brevo before setting EMAIL_SENDER_VERIFIED=true.")
    try:
        sender = validate_email(os.getenv("EMAIL_FROM_ADDRESS", "").strip(), check_deliverability=False).normalized
        recipient = validate_email(os.getenv("EMAIL_TEST_RECIPIENT", "").strip(), check_deliverability=False).normalized
    except EmailNotValidError:
        raise EmailServiceError("Set EMAIL_FROM_ADDRESS to your verified sender and EMAIL_TEST_RECIPIENT to your own valid mailbox.") from None
    if any(address.rsplit("@",1)[1].lower() in ("example.com", "example.net", "example.org") for address in (sender,recipient)):
        raise EmailServiceError("Fictional example addresses belong in Mailpit, not the live email test.")
    return {"key":key, "sender":sender, "recipient":recipient}


def send_connection_test(*, confirmed=False):
    if confirmed is not True:
        raise EmailServiceError("Explicit confirmation is required before sending a real email.")
    values = validate_configuration()
    try:
        with httpx.Client(timeout=httpx.Timeout(15, connect=5), follow_redirects=False, trust_env=False) as client:
            reply = client.post("https://api.brevo.com/v3/smtp/email",
                headers={"api-key":values["key"], "Accept":"application/json", "Content-Type":"application/json"},
                json={"sender":{"email":values["sender"], "name":"ENWEN"}, "to":[{"email":values["recipient"]}],
                      "subject":TEST_SUBJECT, "textContent":TEST_BODY})
        if reply.status_code >= 500 or reply.status_code in (408,429):
            raise EmailServiceError("Email acceptance is uncertain. Check Brevo and your inbox before retrying; nothing was automatically resent.")
        if reply.status_code != 201:
            raise EmailServiceError("Brevo did not accept this email. Check the verified sender, account activation and sending allowance. Nothing was retried.")
        reference = reply.json().get("messageId")
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 512:
            raise EmailServiceError("Email acceptance could not be confirmed. Check Brevo and your inbox before retrying.")
        return {"provider":"brevo", "status":"provider_accepted", "message_id":reference, "delivery_confirmed":False}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise EmailServiceError("Email delivery is uncertain. Check Brevo and your inbox before retrying. No automatic retry was made.") from None
