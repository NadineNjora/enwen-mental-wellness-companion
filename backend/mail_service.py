import re
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from smtplib import SMTP, SMTPException


class TestEmailDeliveryError(RuntimeError):
    pass


def send_test_email(*, recipient: str, subject: str, body: str) -> None:
    recipient = recipient.strip().lower()

    # Intentionally limited to simple, fictional test addresses.
    if len(recipient) > 254 or not re.fullmatch(
        r"[a-z0-9]+(?:[._+-][a-z0-9]+)*@example\.com",
        recipient,
    ):
        raise ValueError(
            "Test mode only accepts fictional @example.com recipients."
        )

    message = EmailMessage()
    message["From"] = "ENWEN Test <no-reply@example.com>"
    message["To"] = recipient
    message["Subject"] = "[ENWEN TEST] " + subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain="example.com")
    message.set_content(
        "LOCAL PROTOTYPE TEST: no real email delivery.\n\n" + body
    )

    try:
        # Fixed local address: never Gmail, Yahoo or an external mail server.
        with SMTP("127.0.0.1", 1025, timeout=5) as smtp:
            smtp.send_message(message)
    except (OSError, SMTPException):
        raise TestEmailDeliveryError(
            "Could not confirm test-email capture. Check Docker and Mailpit, "
            "then check the inbox before retrying. Nothing was retried automatically."
        ) from None


if __name__ == "__main__":
    try:
        send_test_email(
            recipient="trusted.friend@example.com",
            subject="Your ENWEN test inbox is connected",
            body=(
                "This is a fictional connection test. "
                "There is no invitation link or safety alert yet."
            ),
        )
    except TestEmailDeliveryError as error:
        print(error)
        raise SystemExit(1)

    print("Test email captured. Open http://127.0.0.1:8025 to view it.")