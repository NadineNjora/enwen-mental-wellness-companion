"""Run manually to send ONE neutral connection test to your own phone."""
from sms_service import SmsError, TEST_MESSAGE, send_connection_test, validate_configuration


def main():
    try:
        values = validate_configuration()
        print("Destination: your configured phone ending", values["recipient"][-4:])
        print("Message:", TEST_MESSAGE)
        print("This uses live provider credit. Use only your own phone for this connection test.")
        if input("Type SEND OWN TEST to send exactly one SMS: ").strip() != "SEND OWN TEST":
            print("Cancelled. No SMS sent.")
            return
        result = send_connection_test(confirmed=True)
        print("Provider accepted the request. This is not proof of delivery; check your phone and provider dashboard.")
        if result["message_id"]: print("Provider reference:", result["message_id"])
    except SmsError as error:
        print(error)
        raise SystemExit(1)


if __name__ == "__main__": main()
