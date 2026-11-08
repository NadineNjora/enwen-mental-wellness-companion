# Private chat history and support workflow — 7 November 2026

## Working prototype behaviour

- New conversations record the student's acknowledgement of the current processing/storage notice, its text and the selected processor. Canonical user messages and server replies are saved in PostgreSQL. History is owner-only, paginated, and can be reopened after refresh. Only the selected conversation UUID is held in sessionStorage; transcripts and tokens are not stored there.
- Each message uses a request UUID. Replays return the existing result, while pending or failed attempts are not automatically rerun. Client-supplied assistant history is ignored as canonical context. Previous model context is reconstructed from the owner's saved turns.
- A rule-based prototype screen runs before normal model availability checks, request quotas and generation. Explicit first-person danger/action language, including the fictional test sentence about jumping off a building and several misspellings, pauses ordinary AI. This is a signal screen, not a clinical prediction or a validated risk assessment. It has false-positive and false-negative limitations and requires further supervised evaluation.
- The fixed human-support panel shows the Kenyan emergency contact and Befrienders Kenya details, service-hours information and links to their sources. No emergency number is dialled automatically. Public /safety/support remains available without login. Urgent support can be displayed without saving text when processing acknowledgement is missing, or when recording fails.
- A support-paused conversation remains paused on the server and when reopened. A late ordinary AI result cannot overwrite that intervention. New conversation starts a separate thread; it does not delete history or establish that someone is safe.
- A notification outbox records the actual outcome with idempotency and a ten-minute per-contact cooldown. Confirmed fictional @example.com contacts with current test permission can receive a fixed clearly synthetic email in LOCAL Mailpit only. No chat, journal, mood, account details or phone number is put in that message. Missing, pending, revoked, real or unauthorised contacts are blocked. Uncertain capture is never silently retried or reported as delivered.

## Evidence

The following checks passed with fictional data and existing public database records preserved:

| Suite | Checks |
|---|---:|
| Prototype signal examples and scoped negation | 33 |
| Private history, ownership, replay and interruption | 51 |
| Local notification outbox and permissions | 34 |
| Integrated chat, support and history | 26 |
| Frontend history and safety controller | 15 |
| Accessible support panel and safe links | 13 |

Provider-adapter checks (49), saved-session checks (18), existing invitation checks (88), wellness/journal frontend checks (25), and contact frontend checks (11) also passed during integration. These tests are not evidence of clinical accuracy.

The live browser test used the Demo Student account and the explicit fictional sentence. It displayed the support response, disabled ordinary composition and showed the correct no-contact outcome. Reloading restored that same private conversation and support pause, while login remained active. The fictional conversation is intentionally present in this demonstration account; older messages were preserved.

Screenshot: ENWEN-tutorials/10-prototype-walkthrough/safety-history-2026-11-07.png, outside the Git repository.

The opt-in tests/demo_local_safety_capture.py was deliberately run against local Mailpit. ONE fixed synthetic email was captured; repeating the same request created no second send. Its fictional account/contact/outbox data existed only in PostgreSQL TEMP tables and was rolled back. No real person or phone was contacted. The synthetic demonstration email remains in Mailpit.

## Remaining work — do not present as complete

Real trusted-contact SMS is not configured: the student has not created a live provider account, funded credit, or obtained sender approval. Existing email test acceptance does not verify phone ownership or grant live alert permission. Live phone enrollment/verification, recipient agreement, withdrawal, durable delivery tracking and an agreed human response process remain required before live contact alerts.

The screening rules do not understand every expression, language, typo, quotation or context. There is no validated clinical risk model, no emergency dispatch, no guarantee of human response and no automatic escalation to emergency services. User testing, supervised safety evaluation, deployment and any agreed peer-journal/PWA/admin requirements remain separate tasks. No 80% or full-completion claim is made without the approved requirements and rubric.

## Demonstration steps

1. Keep Ollama, PostgreSQL and FastAPI running. Open ENWEN and sign in to a fictional account.
2. In Let's talk, read and acknowledge the saved-chat notice before ordinary messages. Send a fictional everyday message; refresh and reopen it from Your conversations.
3. Choose New conversation and submit the fictional danger test. It should show human support instead of an ordinary Llama response.
4. Refresh again. The selected support-paused conversation should return.
5. For local notification capture, use a confirmed fictional contact and current test permission. A missing/unconfirmed contact must show a blocked outcome, not a false success. Use a new fictional thread to test another event; cooldown prevents repeated notification spam.
6. Open http://127.0.0.1:8025/ for the fixed synthetic email demonstration. Do not describe it as a real emergency SMS.

## Contact/source record

- Kenya emergency numbers: National Police Service service standards, https://www.nationalpolice.go.ke/sites/default/files/2025-01/NPS%20Service%20Standards.pdf (official search result explicitly lists 999/112/911; direct PDF fetch timed out).
- Befrienders Kenya details: verified with the connected local-helpline lookup on 6 November 2026, including Monday–Friday 9 am–5 pm and its exact call/website links. No 24-hour availability was inferred.
- Scope of prediction claims: NICE NG225 recommendations on not using scales/tools to predict future suicide or repeated self-harm, https://www.nice.org.uk/guidance/ng225/chapter/recommendations .

This work was initially local and uncommitted, then included in local commit e51a4e1. Existing .env secrets remain ignored by Git. No real SMS, public publishing or GitHub push occurred in that checkpoint. The 8 November saved-chat management checkpoint adds deliberate transcript removal with content-free replay protection; it does not enable real SMS.
