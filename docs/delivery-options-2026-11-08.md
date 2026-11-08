# Email, alternative SMS and support-screen checkpoint — 8 November 2026

## Three tasks completed in code

1. A selectable Twilio connector was added to the own-phone SMS connection-test script. Africa's Talking remains available; there is no automatic fallback. Both require explicit live settings and a deliberate manual confirmation. Only one fixed neutral message can be submitted per confirmed script invocation. No app request calls this test script.
2. A separate Brevo transactional-email connector and own-mailbox test script were added. They require live settings, a verified sender/account and explicit confirmation. Existing Mailpit invitations and local support notifications remain local even if live email settings are added. Neither connector sends chat, journal or mood text.
3. The existing rule-based screen around Llama was expanded for additional explicit first-person examples, including gerunds, thoughts of self-harm, not wanting to live, explicit plans and reported overdose. This is not a clinically validated Llama classifier, diagnosis, semantic-understanding guarantee or suicide prediction. Ambiguous phrases and languages can still be missed or incorrectly flagged. Supervised evaluation remains required.

The support path runs before ordinary AI generation/model readiness. It pauses the composer, supplies the fixed human-support information and retains the pause in saved history. A late ordinary response is suppressed. No model is allowed to claim that somebody was contacted. Local notification capture/blocked/uncertain outcomes remain distinct from real delivery.

## Verification

- 61 synthetic Twilio/Brevo/local-mail checks passed: disabled/missing settings, invalid recipients/senders, official endpoints, neutral payloads, provider errors, redirects, timeouts, no retries, no credential echoes and no diversion of Mailpit mail.
- 55 phrase examples/checks passed, including ordinary/negated/academic examples. These are regression examples, not a measured clinical sensitivity/specificity claim.
- 32 integrated chat/support/history checks passed with fake AI/SMTP and PostgreSQL TEMP tables rolled back. The expanded urgent examples also work without AI availability or processing acknowledgement, without saving text or sending an alert.
- Existing 49 AI/SMS checks and 13 support-panel checks passed.

Provider transports were mocked throughout these checks. No real SMS, real email, provider signup, payment or API-key creation was performed. User environment secrets were not replaced and live switches remain disabled unless separately configured by the developer. Provider-accepted responses are never labelled proof of device/inbox delivery.

The running FastAPI app was restarted to load the tested screen changes. A live browser demonstration submitted the explicitly fictional sentence `Fictional project test only: I am thinking about killing myself.` with processing acknowledgement unchecked. It displayed the fixed human-support response, support links and truthful no-alert outcome, and disabled ordinary composition. The response reported that the event was not saved. Evidence: ENWEN-tutorials/10-prototype-walkthrough/expanded-support-screen-2026-11-08.png, outside the repository. This was a fictional workflow check, not an assessment of the developer's wellbeing.

## Setup in the developer's own accounts

The developer must complete signup, verification and any payment themselves. Never paste passwords, OTPs, keys, tokens, phone numbers or mailbox addresses into public source or chat. Put required values only in ignored backend/.env; do not replace existing database/JWT settings with the example file.

### Twilio

Start at https://www.twilio.com/try-twilio and verify the account and own test phone as directed. Check Kenya routing and an authorised sender. Current Twilio documentation describes new trial restrictions including verified recipients, signup-country limitations and predefined content. This connector sends custom neutral ENWEN text; a template-only trial may require upgrading before it can be used. The provider Console's supported trial template can be explored separately. Do not claim free custom SMS or bypass account/country restrictions.

Once the account is authorised for this custom message and sender route, add privately:

```dotenv
SMS_PROVIDER=twilio
SMS_MODE=live
LIVE_SMS_ENABLED=true
TWILIO_ACCOUNT_SID=<your own account SID>
TWILIO_AUTH_TOKEN=<your own auth token>
TWILIO_FROM=<your authorised sender or number>
TWILIO_SENDER_APPROVED=true
SMS_TEST_RECIPIENT=<your own Kenyan mobile in +254 format>
```

From backend, run `.\.venv\Scripts\python.exe send_sms_test.py`. It previews the fixed text and requires typing `SEND OWN TEST`. This sends one live request, may use provider credit, and is not a contact-alert test. Check the phone and provider dashboard before retrying after any uncertainty. Disable the live switches after the deliberate test if not continuing setup.

### Brevo

Start at https://www.brevo.com/ and complete account/email verification. Enable transactional email and verify the sender as required. An authenticated domain you control is the reliable sender setup. A recipient may use Gmail/Yahoo/Outlook; this does not mean ENWEN can authenticate those providers' domains as its sender. Brevo documents possible replacement of unauthenticated/free sender addresses; confirm the actual sender/account behaviour in your dashboard.

Add privately only after the sender/account is ready:

```dotenv
EMAIL_PROVIDER=brevo
EMAIL_MODE=live
LIVE_EMAIL_ENABLED=true
BREVO_API_KEY=<your own Brevo API key>
EMAIL_FROM_ADDRESS=<your verified sender>
EMAIL_TEST_RECIPIENT=<your own mailbox>
EMAIL_SENDER_VERIFIED=true
```

From backend, run `.\.venv\Scripts\python.exe send_email_test.py`. It previews the fixed text and requires typing `SEND OWN EMAIL TEST`. Check the real inbox/spam folder and provider dashboard. Acceptance is not an inbox-delivery guarantee. This script does not send a trusted-contact invitation or safety notification.

## When real trusted contacts can be notified

A successful own-phone/mailbox connection is the first live transport check, not completion of the contact-alert feature. Live enrollment needs a separate current student disclosure/permission, verified contact endpoint and recipient agreement/revocation. Local Mailpit acceptances do not verify a real mailbox or phone. A reachable HTTPS response page, durable message references/delivery outcomes and a human response process are still needed. Neither adapter is wired into automatic contact alerts at this checkpoint. No promised delivery date is inferred from passing mocked tests.

## Official sources checked 8 November

- Twilio Kenya sender/route guidelines: https://www.twilio.com/en-us/guidelines/ke/sms
- Twilio trial restrictions: https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account
- Twilio Messages API: https://www.twilio.com/docs/messaging/api/message-resource
- Brevo email API: https://developers.brevo.com/reference/send-transac-email
- Brevo transactional email activation: https://help.brevo.com/hc/en-us/articles/115000188150-Troubleshooting-Issues-with-Brevo-SMTP
- Brevo sender-domain guidance: https://help.brevo.com/hc/en-us/articles/14925263522578-Comply-with-Gmail-Yahoo-and-Microsoft-s-requirements-for-email-senders
