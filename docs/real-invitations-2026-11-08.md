# Real email enrollment checkpoint — 8 November 2026

The developer confirmed receipt of one approved, neutral real Brevo test email. The API key is stored only in ignored backend/.env. This proves that particular own-mailbox test, not automatic delivery to all contacts or SMS readiness.

## Added

- Separate live_contact_invitations table and /trusted-contact/live endpoints; old fictional contact decisions remain unchanged.
- Student form under Trusted contact with a fresh real-email disclosure/acknowledgement and deliberate send confirmation. The email shares the student's display name and secure links, not journals, chats or moods.
- A 24-hour, single-use Accept/Decline link and separate recipient withdrawal link. Only token hashes are stored. Link secrets use URL fragments and are removed from the response page's address without being put in browser storage. Opening a link alone does not record a decision.
- Current recipient notice/acknowledgement, accepted/declined/expired/revoked enrollment status, owner-only status and withdrawal. An acceptance cannot enable automatic safety emails or SMS. Decline/withdrawal remain available separately.
- Durable claim before delivery, owner/request UUID replay protection, one-minute cooldown and five-invitation daily limit. Provider acceptance is distinguished from uncertain outcomes. There is no automatic retry. Sent email cannot be recalled; revocation invalidates its response links.
- Separate public response page and API. Private APIs remain uncached by the service worker. No live delivery switch was enabled, contact details imported or real invitation sent during implementation.

## Verified

36 backend enrollment checks passed with rolled-back PostgreSQL TEMP records and fake mail: acknowledgement, deployment validation, hashes, expiry, single use, acceptance, withdrawal, account isolation, cooldown, unchanged public data, replay and uncertain delivery. Existing local-contact backend checks (90), contact dashboard checks (11), local recipient-page checks (7) and delivery-connector checks (61) passed. New real recipient-page behaviour has an isolated browser/API test suite. JavaScript syntax and Git whitespace checks passed.

The local FastAPI server was restarted with the routes. Browser visual verification timed out; no completed live-browser visual review of the new form is claimed. No real contact invitation or recipient acceptance was performed. Existing records were preserved, and the new table was created additively.

## Blocking dependency and next task

Real invitations are deliberately disabled until the app has a reachable public HTTPS origin. A localhost email link cannot work on a trusted person's separate device. Deploy the application/backend/database appropriately, verify the response page from another device, then configure PUBLIC_APP_URL to the deployment origin and LIVE_CONTACT_EMAIL_ENABLED=true. The sender/API settings must also be valid. Do not insert a made-up domain or expose the local server/database/Ollama without a deployment review. Deployment also needs a plan for the current laptop-only Llama service.

After deployment, use an explicitly authorised recipient for one real invitation and verify acceptance, decline and withdrawal before enabling the feature more widely. Automatic wellness-alert delivery remains a separate unfinished feature requiring fresh live-alert permission, validated recipient eligibility, delivery handling and an agreed human response process. The action-language screen remains a prototype, not clinically validated risk detection.

SMS is a separate paid transport: Brevo requires prepaid SMS credits and, for new accounts, sender registration for each destination country. The account previously showed zero SMS credits. No SMS credit purchase or sender approval was performed. Check the account's Kenya price quote before buying; no exact amount or approval time is promised.

Sources: https://help.brevo.com/hc/en-us/articles/208717449-Supported-countries-and-pricing-for-SMS-messages and https://help.brevo.com/hc/en-us/articles/4424272648850-Send-transactional-SMS .
