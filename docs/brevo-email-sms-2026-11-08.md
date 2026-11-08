# One Brevo account for email and SMS — 8 November 2026

The developer confirmed that only account creation is complete. Email sender verification, transactional email activation/domain setup, SMS sender registration for Kenya, SMS credit and private API configuration have not been confirmed. Nothing was enabled or sent to a real person in this checkpoint.

## Code ready for deliberate connection tests

- The existing email connection-test adapter uses Brevo's HTTPS email API.
- SMS_PROVIDER=brevo now selects Brevo's transactional SMS API through the existing send_sms_test.py. The developer must explicitly confirm a neutral own-phone test; no app route invokes it automatically.
- The SMS adapter requires SMS_MODE=live, LIVE_SMS_ENABLED=true, a private BREVO_API_KEY, an approved BREVO_SMS_SENDER and BREVO_SMS_SENDER_APPROVED=true. The latter flag records the developer's confirmation of provider approval; it does not query or prove approval. Email verification cannot enable SMS by itself.
- Kenyan own-phone numbers are configured as +254... and sent as country-code digits according to the provider's documented SMS request format. Sender IDs are restricted to 1–11 ASCII letters/digits with at least one letter. No spaces, punctuation or emoji are accepted.
- Only fixed neutral test text is sent. No chat, journals, moods, student identity, contact invitation or user-selected content is included.
- Errors/timeouts are redacted and never trigger retries or fallback providers. A valid 201 message reference means provider acceptance, not handset delivery. Existing Mailpit invitation/support transport remains local.

## Next student action: verify the email sender

Verification passed with synthetic credentials and mocked transports: 53 Brevo SMS checks, 61 existing live-connector checks and 49 existing AI/SMS checks. These checks made no real provider requests or sends and do not establish that this Brevo account has sending permission.

In Brevo, open Settings > Senders, Domains, IPs > Senders > Add a sender. Use ENWEN for the From name and an address the developer controls for From email. Save and complete the emailed verification-code step privately. Sender verification does not authenticate a free mailbox provider's domain; follow any domain/account requirements shown by Brevo. Do not enter a fabricated ENWEN domain or share verification codes/API keys in chat.

Once the sender/account is verified, the existing own-mailbox test can be configured privately. Before live trusted-contact invitations, enrollment/recipient agreement and a reachable secure response page still need implementation. Current local invitations are not redirected by these settings.

## Later SMS setup

For new accounts Brevo requires sender registration for each destination country. Confirm Kenya sender approval and the displayed SMS credit price before purchasing. Once approved, add the following to the existing private backend/.env without replacing database/JWT settings:

```dotenv
SMS_PROVIDER=brevo
SMS_MODE=live
LIVE_SMS_ENABLED=true
BREVO_API_KEY=<your private API key, not an SMTP password>
BREVO_SMS_SENDER=<exact approved sender>
BREVO_SMS_SENDER_APPROVED=true
SMS_TEST_RECIPIENT=<your own Kenyan number in +254 format>
```

Run `.\.venv\Scripts\python.exe send_sms_test.py` from backend only when ready for a real provider request. The command previews the fixed message and requires typing SEND OWN TEST. Check the phone and provider dashboard before any manual retry. Do not use a trusted person's number for this own-phone connection test. No live credentials or recipients were added during implementation, and the example configuration leaves sending disabled.

Automatic live contact alerts, phone verification, fresh live permission, recipient withdrawal, durable delivery handling and public HTTPS deployment remain unfinished. The neutral connector is not the completed emergency-notification feature.

## Official references

- Sender creation: https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email
- Transactional SMS request/201 reference: https://developers.brevo.com/docs/transactional-sms-endpoints
- New-account sender registration: https://help.brevo.com/hc/en-us/articles/4424272648850-Send-transactional-SMS
- Kenya coverage and SMS credit pricing: https://help.brevo.com/hc/en-us/articles/208717449-Supported-countries-and-pricing-for-SMS-messages
