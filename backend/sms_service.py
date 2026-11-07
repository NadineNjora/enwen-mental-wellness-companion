"""Live SMS connection test only. Not a risk classifier or contact-alert flow."""
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))
TEST_MESSAGE = "ENWEN connection test. This is not a safety alert."


class SmsError(RuntimeError):
    pass


def configuration():
    return {"username":os.getenv("AT_USERNAME", "").strip(),
            "api_key":os.getenv("AT_API_KEY", "").strip(),
            "sender":os.getenv("AT_SENDER_ID", "").strip(),
            "recipient":os.getenv("SMS_TEST_RECIPIENT", "").strip()}


def validate_configuration():
    values = configuration()
    if os.getenv("SMS_MODE", "disabled").lower() != "live" or os.getenv("LIVE_SMS_ENABLED", "false").lower() != "true":
        raise SmsError("Live SMS is disabled. Set SMS_MODE=live and LIVE_SMS_ENABLED=true only when ready for a paid connection test.")
    if not values["username"] or values["username"].lower() == "sandbox" or not values["api_key"]:
        raise SmsError("Set your live AT_USERNAME and AT_API_KEY. Sandbox credentials cannot send to a real phone.")
    if not values["sender"]:
        raise SmsError("Set AT_SENDER_ID to the sender authorised by your provider.")
    if not re.fullmatch(r"\+254[17]\d{8}", values["recipient"]):
        raise SmsError("Set SMS_TEST_RECIPIENT to your own Kenyan mobile in +254 format, with no spaces.")
    return values


def send_connection_test(*, confirmed=False):
    if confirmed is not True:
        raise SmsError("Explicit confirmation is required before sending a real SMS.")
    values = validate_configuration()
    try:
        with httpx.Client(timeout=httpx.Timeout(15, connect=5), follow_redirects=False) as client:
            reply = client.post("https://api.africastalking.com/version1/messaging",
                headers={"apiKey":values["api_key"], "Accept":"application/json"},
                data={"username":values["username"], "to":values["recipient"], "from":values["sender"],
                      "message":TEST_MESSAGE, "bulkSMSMode":1})
        if reply.status_code not in (200, 201):
            raise SmsError("SMS request failed. Check live credentials, sender approval and credit in the provider dashboard. Nothing was retried.")
        recipients = reply.json()["SMSMessageData"]["Recipients"]
        if (not isinstance(recipients, list) or len(recipients) != 1
                or not isinstance(recipients[0], dict)
                or str(recipients[0].get("statusCode")) != "101"):
            raise SmsError("Provider did not accept the SMS. Check the dashboard before retrying.")
        return {"status":"provider_accepted", "message_id":recipients[0].get("messageId"),
                "delivery_confirmed":False}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
        raise SmsError("SMS delivery is uncertain. Check the provider dashboard and your phone before retrying. No automatic retry was made.") from None
