"""Synthetic Brevo SMS adapter checks. No provider request or real SMS."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
import httpx
import sms_service as sms

checks=[]
def check(name, condition):
    assert condition,name
    checks.append(name)
def rejects(name, action, fragment=None):
    try:
        action()
        raise AssertionError(name + " did not reject")
    except sms.SmsError as error:
        assert "synthetic-private" not in str(error),name
        if fragment: assert fragment in str(error),name
        checks.append(name)

settings={"SMS_PROVIDER":"brevo","SMS_MODE":"live","LIVE_SMS_ENABLED":"true",
          "BREVO_API_KEY":"synthetic-private-brevo-key","BREVO_SMS_SENDER":"ENWEN",
          "BREVO_SMS_SENDER_APPROVED":"true","SMS_TEST_RECIPIENT":"+254700000001"}
with patch.dict(os.environ,settings,clear=True),patch.object(sms.httpx,"Client") as constructor:
    transport=constructor.return_value.__enter__.return_value
    rejects("confirmation required",lambda:sms.send_connection_test())
    for key,value,label in (("SMS_MODE","disabled","disabled mode"),("LIVE_SMS_ENABLED","false","disabled flag"),
        ("BREVO_API_KEY","","missing key"),("BREVO_SMS_SENDER_APPROVED","false","unapproved SMS sender"),
        ("BREVO_SMS_SENDER","","empty sender"),("BREVO_SMS_SENDER","1234","numeric-only sender"),
        ("BREVO_SMS_SENDER","TooLongSenderName","long sender"),("BREVO_SMS_SENDER","EN WEN","sender spaces"),
        ("BREVO_SMS_SENDER","ENWEN!","sender punctuation"),("BREVO_SMS_SENDER","ENWEN🌷","sender emoji"),
        ("SMS_TEST_RECIPIENT","+15550000001","non-Kenyan recipient"),("SMS_TEST_RECIPIENT","0700000001","local-format recipient")):
        with patch.dict(os.environ,{key:value}):rejects(label+" blocked",lambda:sms.send_connection_test(confirmed=True))
    with patch.dict(os.environ,{"BREVO_SMS_SENDER_APPROVED":"false","EMAIL_SENDER_VERIFIED":"true"}):
        rejects("email verification cannot approve SMS",lambda:sms.send_connection_test(confirmed=True))
    check("validation opens no transport",constructor.call_count==0)
    transport.post.return_value=httpx.Response(201,json={"messageId":1511882900100020})
    result=sms.send_connection_test(confirmed=True)
    check("numeric reference preserved as string",result["message_id"]=="1511882900100020")
    check("acceptance never labelled confirmed delivery",result["provider"]=="brevo" and result["status"]=="provider_accepted" and result["delivery_confirmed"] is False)
    call=transport.post.call_args
    check("fixed official SMS endpoint",call.args[0]=="https://api.brevo.com/v3/transactionalSMS/send")
    check("recipient converted to documented country-code digits",call.kwargs["json"]["recipient"]=="254700000001")
    check("fixed neutral transactional content only",call.kwargs["json"]=={"sender":"ENWEN","recipient":"254700000001","content":sms.TEST_MESSAGE,"type":"transactional","tag":"enwen-own-phone-test"})
    check("no credential in SMS payload",settings["BREVO_API_KEY"] not in str(call.kwargs["json"]))
    check("key sent only in appropriate header",call.kwargs["headers"]["api-key"]==settings["BREVO_API_KEY"])
    check("no redirect or environment-proxy credential forwarding",constructor.call_args.kwargs["follow_redirects"] is False and constructor.call_args.kwargs["trust_env"] is False)
    for status in (400,401,402,403,429,500,503,302):
        transport.post.return_value=httpx.Response(status,json={"message":"synthetic-private-brevo-key"})
        before=transport.post.call_count
        rejects("HTTP "+str(status)+" gives redacted error",lambda:sms.send_connection_test(confirmed=True))
        check("HTTP "+str(status)+" never retries or falls back",transport.post.call_count==before+1 and transport.post.call_args.args[0]=="https://api.brevo.com/v3/transactionalSMS/send")
    for reference in (None,True,False,0,-1,"","bad",{},[],"1"*33):
        transport.post.return_value=httpx.Response(201,json={"messageId":reference})
        rejects("invalid message reference rejected: "+repr(reference),lambda:sms.send_connection_test(confirmed=True))
    transport.post.return_value=httpx.Response(201,json={"messageId":"1511882900100020"})
    check("numeric string reference accepted",sms.send_connection_test(confirmed=True)["message_id"]=="1511882900100020")
    transport.post.return_value=httpx.Response(201,text="not JSON")
    rejects("malformed response stays uncertain",lambda:sms.send_connection_test(confirmed=True),"uncertain")
    transport.post.side_effect=httpx.ReadTimeout("synthetic-private-brevo-key")
    before=transport.post.call_count
    rejects("timeout redacted and uncertain",lambda:sms.send_connection_test(confirmed=True),"uncertain")
    check("timeout never retries",transport.post.call_count==before+1)
print(f"Passed {len(checks)} Brevo SMS checks. Fake transport only; no real SMS sent.")
for name in checks:print("PASS:",name)
