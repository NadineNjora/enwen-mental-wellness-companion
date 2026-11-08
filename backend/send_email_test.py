"""Manually send ONE fixed neutral email to the developer's own mailbox."""
from email_service import EmailServiceError, TEST_BODY, TEST_SUBJECT, send_connection_test, validate_configuration


def main():
    try:
        validate_configuration()
        print("Destination: your privately configured own mailbox.")
        print("Subject:", TEST_SUBJECT)
        print("Message:", TEST_BODY)
        print("This makes one live provider request and uses your account's sending allowance.")
        if input("Type SEND OWN EMAIL TEST to send exactly one email: ").strip() != "SEND OWN EMAIL TEST":
            print("Cancelled. No email sent.")
            return
        send_connection_test(confirmed=True)
        print("Brevo accepted the request. This is not proof of inbox delivery; check your inbox, spam folder and provider dashboard.")
    except EmailServiceError as error:
        print(error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
