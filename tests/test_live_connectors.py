"""Synthetic Twilio/Brevo transport checks: no external requests, SMS or email."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
import httpx
import email_service as email
import sms_service as sms
import mail_service as local_mail

checks=[]
def check(name, condition):
    assert condition, name
    checks.append(name)
def rejects(name, error_type, action, contains=None):
    try:
        action()
        raise AssertionError(name + " should reject")
    except error_type as error:
        if contains: assert contains in str(error), name
        assert "synthetic-private" not in str(error), name + " leaked a credential"
        checks.append(name)

twilio={"SMS_PROVIDER":"twilio","SMS_MODE":"live","LIVE_SMS_ENABLED":"true",
        "TWILIO_ACCOUNT_SID":"AC"+"1"*32,"TWILIO_AUTH_TOKEN":"2"*32,"TWILIO_FROM":"+15550000001",
        "TWILIO_SENDER_APPROVED":"true","SMS_TEST_RECIPIENT":"+254700000001"}
brevo={"EMAIL_PROVIDER":"brevo","EMAIL_MODE":"live","LIVE_EMAIL_ENABLED":"true",
       "BREVO_API_KEY":"synthetic-private-email-key","EMAIL_FROM_ADDRESS":"sender@enwen-demonstration.dev",
       "EMAIL_TEST_RECIPIENT":"owner@enwen-demonstration.dev","EMAIL_SENDER_VERIFIED":"true"}
with patch.dict(os.environ,twilio,clear=True), patch.object(sms.httpx,"Client") as constructor:
    transport=constructor.return_value.__enter__.return_value
    rejects("SMS needs deliberate confirmation",sms.SmsError,lambda:sms.send_connection_test())
    for key,value,label in (("LIVE_SMS_ENABLED","false","disabled SMS"),("TWILIO_ACCOUNT_SID","","missing account"),
        ("TWILIO_AUTH_TOKEN","bad","invalid token"),("TWILIO_SENDER_APPROVED","false","unapproved sender"),
        ("TWILIO_FROM","bad sender !","invalid sender"),("SMS_TEST_RECIPIENT","+15550000002","non-Kenyan test recipient"),
        ("SMS_PROVIDER","unknown","unknown provider")):
        with patch.dict(os.environ,{key:value}):
            rejects(label+" makes no send",sms.SmsError,lambda:sms.send_connection_test(confirmed=True))
    check("SMS validation never opens transport",constructor.call_count==0)
    transport.post.return_value=httpx.Response(201,json={"sid":"SM"+"3"*32,"status":"queued"})
    accepted=sms.send_connection_test(confirmed=True)
    check("Twilio queued acceptance is not delivery",accepted["provider"]=="twilio" and accepted["status"]=="provider_accepted" and accepted["delivery_confirmed"] is False)
    call=transport.post.call_args
    check("Twilio uses fixed official endpoint",call.args[0]=="https://api.twilio.com/2010-04-01/Accounts/"+twilio["TWILIO_ACCOUNT_SID"]+"/Messages.json")
    check("SMS body is fixed neutral text only",call.kwargs["data"]=={"To":twilio["SMS_TEST_RECIPIENT"],"From":twilio["TWILIO_FROM"],"Body":sms.TEST_MESSAGE})
    check("Twilio credentials use Basic Auth",isinstance(call.kwargs["auth"],httpx.BasicAuth))
    check("SMS disallows redirects and environment proxies",constructor.call_args.kwargs["follow_redirects"] is False and constructor.call_args.kwargs["trust_env"] is False)
    for status,label in ((400,"Twilio rejection"),(401,"Twilio invalid credentials"),(429,"Twilio limit"),(503,"Twilio outage"),(302,"Twilio redirect")):
        transport.post.return_value=httpx.Response(status,json={"message":"synthetic-private-token must not appear"})
        before=transport.post.call_count
        rejects(label+" is not reported delivered",sms.SmsError,lambda:sms.send_connection_test(confirmed=True))
        check(label+" is not retried",transport.post.call_count==before+1)
    for data,label in (({"sid":"bad","status":"queued"},"bad SMS reference"),({"sid":"SM"+"3"*32,"status":"failed"},"failed SMS"),(None,"empty SMS response")):
        transport.post.return_value=httpx.Response(201,json=data)
        rejects(label+" not accepted",sms.SmsError,lambda:sms.send_connection_test(confirmed=True))
    transport.post.side_effect=httpx.ReadTimeout("synthetic-private-token")
    before=transport.post.call_count
    rejects("SMS timeout redacted and uncertain",sms.SmsError,lambda:sms.send_connection_test(confirmed=True),"uncertain")
    check("SMS timeout never retries",transport.post.call_count==before+1)

with patch.dict(os.environ,brevo,clear=True), patch.object(email.httpx,"Client") as constructor:
    transport=constructor.return_value.__enter__.return_value
    rejects("email needs deliberate confirmation",email.EmailServiceError,lambda:email.send_connection_test())
    for key,value,label in (("LIVE_EMAIL_ENABLED","false","disabled email"),("EMAIL_MODE","test","non-live mode"),
        ("BREVO_API_KEY","","missing email key"),("EMAIL_SENDER_VERIFIED","false","unverified sender"),
        ("EMAIL_FROM_ADDRESS","bad","invalid from"),("EMAIL_TEST_RECIPIENT","bad","invalid recipient"),
        ("EMAIL_TEST_RECIPIENT","person@example.com","fictional recipient"),("EMAIL_PROVIDER","unknown","unknown email provider")):
        with patch.dict(os.environ,{key:value}):
            rejects(label+" makes no send",email.EmailServiceError,lambda:email.send_connection_test(confirmed=True))
    check("email validation never opens transport",constructor.call_count==0)
    transport.post.return_value=httpx.Response(201,json={"messageId":"synthetic-brevo-reference"})
    accepted=email.send_connection_test(confirmed=True)
    check("Brevo acceptance is not delivery",accepted["provider"]=="brevo" and accepted["status"]=="provider_accepted" and accepted["delivery_confirmed"] is False)
    call=transport.post.call_args
    check("email uses fixed official HTTPS endpoint",call.args[0]=="https://api.brevo.com/v3/smtp/email")
    check("email has only one configured recipient",call.kwargs["json"]["to"]==[{"email":brevo["EMAIL_TEST_RECIPIENT"]}])
    check("email contains neutral test and no invitation or health text",call.kwargs["json"]["textContent"]==email.TEST_BODY and call.kwargs["json"]["subject"]==email.TEST_SUBJECT)
    check("email redirects and environment proxies disabled",constructor.call_args.kwargs["follow_redirects"] is False and constructor.call_args.kwargs["trust_env"] is False)
    for status,label in ((400,"Brevo rejection"),(401,"Brevo invalid key"),(429,"Brevo limit"),(503,"Brevo outage"),(302,"Brevo redirect")):
        transport.post.return_value=httpx.Response(status,json={"message":"synthetic-private-email-key"})
        before=transport.post.call_count
        rejects(label+" not reported delivered",email.EmailServiceError,lambda:email.send_connection_test(confirmed=True))
        check(label+" not retried",transport.post.call_count==before+1)
    for data in ({},None,{"messageId":42}):
        transport.post.return_value=httpx.Response(201,json=data)
        rejects("malformed Brevo acceptance blocked",email.EmailServiceError,lambda:email.send_connection_test(confirmed=True))
    transport.post.side_effect=httpx.ReadTimeout("synthetic-private-email-key")
    before=transport.post.call_count
    rejects("email timeout redacted and uncertain",email.EmailServiceError,lambda:email.send_connection_test(confirmed=True),"uncertain")
    check("email timeout never retries",transport.post.call_count==before+1)

# Even with live flags, existing fictional invitations must stay local.
with patch.dict(os.environ,{**twilio,**brevo},clear=True),patch.object(local_mail,"SMTP") as smtp,patch.object(httpx,"Client") as rest:
    local_mail.send_test_email(recipient="fictional@example.com",subject="Synthetic",body="Synthetic local capture only")
    check("live flags cannot redirect local test email",smtp.call_args.args==("127.0.0.1",1025) and not rest.called)
    rejects("local mail still rejects real recipients",ValueError,lambda:local_mail.send_test_email(recipient=brevo["EMAIL_TEST_RECIPIENT"],subject="Synthetic",body="Never sent"))
print(f"Passed {len(checks)} live-connector checks. All provider and SMTP transports were mocked; no real messages sent.")
for name in checks:print("PASS:",name)
