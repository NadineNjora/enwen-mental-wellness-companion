# Local email presentation checkpoint — 8 November 2026

This updates the earlier functional-completion report. ENWEN now supports an explicitly configured laptop demonstration with real Brevo email. This is not public deployment. SMS remains on hold.

## Implemented

- Local presentation invitation links use http://127.0.0.1:8000 and must be opened on the computer hosting ENWEN.
- The configured demonstration student is the only account permitted to invite the configured demonstration mailbox. That mailbox must match the configured verified sender. Other students/recipients are rejected.
- Invitation and check-in email delivery switches can be enabled locally without pretending a public HTTPS origin exists.
- The recipient must explicitly accept the invitation. The student must separately enable the current check-in notice for that exact enrollment. Existing fictional contacts do not provide this permission.
- The chat safety screen interrupts ordinary generation. In presentation mode, the email body and subject are fixed, clearly synthetic, report no real emergency and contain no student message text.
- At most one accepted or uncertain automatic demonstration email is allowed for the demo account. This cap persists beyond the normal ten-minute production cooldown; replay does not send again. Further demonstrations require a separately authorised change.
- SMS is not invoked. Production still requires a public HTTPS origin and suppresses fictional demonstrations.
- Permission changes use the database wall-clock time so rapid acceptance/withdrawal changes retain their actual order.
- Chat notices now disclose the separate real-email pathway and restricted presentation mode accurately.

## Verification

18 local demonstration checks, 37 functional checks and 36 contact invitation checks passed against temporary PostgreSQL tables and fake email transport. Checks include the chat-to-email path, recipient/account restriction, fresh recipient and student agreement, single-send cap, no private text in demo mail, withdrawal, owner isolation and production origin rules. Original public database record counts were preserved.

The local FastAPI server was restarted with the restricted demonstration configuration. Its database health endpoint returned 200/connected. One explicitly authorised real invitation was accepted by Brevo; enrollment remained pending at this checkpoint. No automatic demonstration check-in email had yet been sent, and no recipient acceptance or student permission was fabricated.

The main page, invitation response page, invitation script and personalised-suggestion endpoint returned 200. An ordinary synthetic Llama conversation completed and its response was saved in PostgreSQL. A verification client using a 55-second timeout stopped waiting before that result; the application allows up to 150 seconds for local requests. First-reply CPU latency remains a presentation consideration; no cloud or paid model fallback was enabled.

### Follow-up: authorised real-email demonstration

The recipient subsequently accepted the real invitation. At the user's explicit direction, the separate student permission was saved through the API and verified as enabled for that accepted enrollment. One authorised fictional chat test then returned HTTP 200 with urgent support and a provider_accepted email outcome. The subject was “ENWEN DEMO: automatic check-in test”; its fixed body reported no real emergency and included no private chat or journal text. The user confirmed receipt in the verified mailbox. No SMS was invoked. This verifies the restricted local demonstration email journey; it does not establish public deployment, emergency response or clinical detection accuracy.

A read-only database check confirmed that the demonstration turn was saved with the support-interruption status, its conversation was paused, and exactly one email outbox record existed for that request with provider_accepted status. This check sent no additional email.

## Operator steps and limits

1. Receive the deliberately requested real invitation in the verified mailbox.
2. On the ENWEN laptop, open its response link, read the notice and choose Accept or Decline. No decision is recorded just by opening it.
3. In Demo Student's Trusted contact page, refresh the real enrollment status and, if agreed, record the separate check-in email permission.
4. Exercise the fictional chat interruption once. Verify the on-screen support panel, provider outcome and actual mailbox receipt separately. Provider acceptance does not prove inbox delivery or a human response.

Private deployment settings and API keys stay in the ignored backend/.env file. No credentials belong in this repository. The local demo cannot substitute for a public recipient journey, real mobile/PWA verification, user acceptance testing or clinical safety evaluation. The rule-based interruption is not a clinically validated risk classifier.
