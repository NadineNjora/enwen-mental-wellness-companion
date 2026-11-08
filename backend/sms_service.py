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


def sms_provider():
    selected = os.getenv("SMS_PROVIDER", "africastalking").strip().lower()
    if selected not in ("africastalking", "twilio", "brevo"):
        raise SmsError("Choose SMS_PROVIDER=brevo, twilio or africastalking. No provider fallback is attempted.")
    return selected


def validate_configuration():
    values = configuration()
    if os.getenv("SMS_MODE", "disabled").strip().lower() != "live" or os.getenv("LIVE_SMS_ENABLED", "false").strip().lower() != "true":
        raise SmsError("Live SMS is disabled. Set SMS_MODE=live and LIVE_SMS_ENABLED=true only when ready for a paid connection test.")
    if not re.fullmatch(r"\+254[17]\d{8}", values["recipient"]):
        raise SmsError("Set SMS_TEST_RECIPIENT to your own Kenyan mobile in +254 format, with no spaces.")
    selected = sms_provider()
    if selected == "brevo":
        key = os.getenv("BREVO_API_KEY", "").strip()
        sender = os.getenv("BREVO_SMS_SENDER", "").strip()
        if not key:
            raise SmsError("Set BREVO_API_KEY privately in backend/.env. Use an API key, not an SMTP password.")
        if not re.fullmatch(r"(?=.{1,11}$)(?=.*[A-Za-z])[A-Za-z0-9]+", sender):
            raise SmsError("Set BREVO_SMS_SENDER to your approved alphanumeric sender: 1-11 letters/digits with at least one letter, no spaces or punctuation.")
        if os.getenv("BREVO_SMS_SENDER_APPROVED", "false").strip().lower() != "true":
            raise SmsError("Register the SMS sender for Kenya and confirm approval in Brevo before setting BREVO_SMS_SENDER_APPROVED=true. Email sender verification is separate.")
        return {"provider":"brevo", "api_key":key, "sender":sender, "recipient":values["recipient"]}
    if selected == "twilio":
        account = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        sender = os.getenv("TWILIO_FROM", "").strip()
        if not re.fullmatch(r"AC[0-9a-fA-F]{32}", account) or not re.fullmatch(r"[0-9a-fA-F]{32}", token):
            raise SmsError("Set your TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN privately in backend/.env.")
        if not (re.fullmatch(r"\+[1-9]\d{6,14}", sender) or re.fullmatch(r"(?=.{1,11}$)(?=.*[A-Za-z])[A-Za-z0-9]+", sender)):
            raise SmsError("Set TWILIO_FROM to the number or sender authorised by Twilio for this route.")
        if os.getenv("TWILIO_SENDER_APPROVED", "false").strip().lower() != "true":
            raise SmsError("Confirm the sender and Kenyan route are authorised in Twilio before setting TWILIO_SENDER_APPROVED=true.")
        return {"provider":"twilio", "account":account, "token":token, "sender":sender, "recipient":values["recipient"]}
    if not values["username"] or values["username"].lower() == "sandbox" or not values["api_key"]:
        raise SmsError("Set your live AT_USERNAME and AT_API_KEY. Sandbox credentials cannot send to a real phone.")
    if not values["sender"]:
        raise SmsError("Set AT_SENDER_ID to the sender authorised by your provider.")
    return values


def _send_brevo_test(values):
    try:
        with httpx.Client(timeout=httpx.Timeout(15, connect=5), follow_redirects=False, trust_env=False) as client:
            reply = client.post("https://api.brevo.com/v3/transactionalSMS/send",
                headers={"api-key":values["api_key"], "Accept":"application/json", "Content-Type":"application/json"},
                json={"sender":values["sender"], "recipient":values["recipient"][1:],
                      "content":TEST_MESSAGE, "type":"transactional", "tag":"enwen-own-phone-test"})
        if reply.status_code >= 500 or reply.status_code in (408, 429):
            raise SmsError("SMS acceptance is uncertain. Check Brevo and your phone before trying again. Nothing was retried.")
        if reply.status_code != 201:
            raise SmsError("Brevo did not accept this SMS. Check SMS activation, Kenyan sender approval, recipient and SMS credits. Nothing was retried.")
        reference = reply.json().get("messageId")
        # Brevo documents an integer ID. Accept its numeric string form too,
        # but never bool, an arbitrary object or an empty/invalid identifier.
        if type(reference) not in (int, str) or not re.fullmatch(r"[1-9]\d{0,31}", str(reference)):
            raise SmsError("Brevo SMS acceptance could not be confirmed. Check its dashboard before retrying.")
        return {"provider":"brevo", "status":"provider_accepted", "message_id":str(reference), "delivery_confirmed":False}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise SmsError("SMS delivery is uncertain. Check Brevo and your phone before retrying. No automatic retry was made.") from None


def _send_twilio_test(values):
    try:
        with httpx.Client(timeout=httpx.Timeout(15, connect=5), follow_redirects=False, trust_env=False) as client:
            reply = client.post("https://api.twilio.com/2010-04-01/Accounts/" + values["account"] + "/Messages.json",
                auth=httpx.BasicAuth(values["account"], values["token"]), headers={"Accept":"application/json"},
                data={"To":values["recipient"], "From":values["sender"], "Body":TEST_MESSAGE})
        if reply.status_code >= 500 or reply.status_code in (408, 429):
            raise SmsError("SMS acceptance is uncertain. Check Twilio and your phone before trying again. Nothing was retried.")
        if reply.status_code != 201:
            raise SmsError("Twilio did not accept this SMS. Check whether your account allows custom message text, recipient verification, Kenyan route permissions, sender approval and credit. Nothing was retried.")
        data = reply.json()
        reference = data.get("sid")
        if (not isinstance(reference, str) or not re.fullmatch(r"SM[0-9a-fA-F]{32}", reference)
                or data.get("status") not in ("accepted", "queued", "sending", "sent", "delivered")):
            raise SmsError("Twilio acceptance could not be confirmed. Check its dashboard before retrying.")
        return {"provider":"twilio", "status":"provider_accepted", "message_id":reference, "delivery_confirmed":False}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise SmsError("SMS delivery is uncertain. Check Twilio and your phone before retrying. No automatic retry was made.") from None


def send_connection_test(*, confirmed=False):
    if confirmed is not True:
        raise SmsError("Explicit confirmation is required before sending a real SMS.")
    values = validate_configuration()
    if values.get("provider") == "brevo":
        return _send_brevo_test(values)
    if values.get("provider") == "twilio":
        return _send_twilio_test(values)
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
