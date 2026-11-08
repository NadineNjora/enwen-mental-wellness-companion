# Functional checkpoint against the proposal — 8 November 2026

The scope was checked against 4thyr proposal.final.docx, especially the aim, specific objectives, scope, system components and evaluation sections. Deployment/backup drafts are supporting work and are not counted as student features. SMS is on hold at the developer's explicit request. No grade or percentage is claimed without the supervisor's rubric.

Subsequent same-day updates: the [restricted local real-email demonstration](local-email-presentation-2026-11-08.md) completed with user-confirmed receipt, [student context and private calendar summaries](student-context-2026-11-08.md) were implemented and verified, and [peer reflections with community-only moderation](community-checkpoint-2026-11-08.md) were added. These supersede the earlier local delivery and peer-journaling status below. Public deployment and broader real-contact operation remain outstanding.

| Promised function | Current implementation | Remaining verification/work |
|---|---|---|
| Accounts, authentication, informed consent | Registration, JWT, revocable saved sessions, owner-only access and separate consent notices | Real user acceptance testing and hosted HTTPS session checks |
| Mood tracking and trends | 1–10 check-ins, original legacy 1–5 records, history and time-based charts | Usability testing with students |
| Private digital journals | Create, list, read, update and delete, draft protection | Usability testing; no peer journals implemented |
| Personalised wellness recommendations | NEW owner-only /wellness/suggestions; latest recorded score selects practical actions and relevant public resources; visible on Home | Check dashboard presentation in real browser after refresh. These are non-diagnostic choices, not clinical scores |
| Llama 3 and source-grounded recommendations | NEW PostgreSQL knowledge_passages store, attributed seed summaries and BM25 retrieval, with limited English/Swahili topic expansion; top passages supplied to the existing Llama 3.2 model | Supervised quality/relevance evaluation. Corpus is curated summaries, not full documents or embedding retrieval; no clinical source approval is claimed |
| Human-support referral | Fixed support screen interrupts ordinary generation and persists safety pause | Rules are not clinically validated and may miss or over-trigger language |
| Trusted-contact real email enrollment | Fresh student notice, recipient Accept/Decline and withdrawal, hashed expiring links | Needs public HTTPS response page and an authorised real-recipient end-to-end test |
| Automated trusted-contact check-in email | NEW live_email_alerts outbox and separate contact-bound live_email_permissions; chat dispatches to it only when deployment flag is enabled and both parties qualify | Live delivery is OFF. No real automatic alert sent; public deployment/recipient acceptance/permission and a supervised live test remain |
| Mobile access | Responsive pages and PWA preparation | Public HTTPS deployment and actual mobile installation/verification |
| Testing and evaluation | Synthetic frontend/backend/temporary-database regression tests; one approved own-mailbox Brevo test confirmed by developer | User acceptance, safety evaluation, hosted end-to-end testing and final documentation |

## New functional behaviour

Personalised suggestions use only the owner's latest check-in score and its original denominator. Existing data is not rescaled. Journal contents and mood notes are not indexed or automatically sent to Llama. Source ranking is BM25 over a bounded public summary corpus in PostgreSQL. Source title, publisher, audience notes and link remain attached; no internet browsing or full-document retrieval is implied.

The current live recipient notice requires agreement to minimal wellbeing check-in emails. Separately, the student must explicitly enable the current live-email notice for that exact accepted enrollment. Replacing/revoking a recipient cannot inherit that permission. The original fictional contact consent is not reused. Current wellness permission, deployment switches and verified sender configuration are checked before delivery. No SMS or emergency dispatch is invoked.

Real alert attempts commit a content-free claim before HTTP transport. Replays never resend, and a ten-minute cooldown limits repeated check-in emails. Provider acceptance is not inbox delivery, an emergency response or a guarantee that a person read the message. Uncertain transport has no automatic retry. Fictional demonstration messages are explicitly blocked from real delivery. The support panel still appears if recording or notification fails.

## Verification at this checkpoint

- 37 new functional integration checks passed with PostgreSQL TEMP tables and fake email, including the chat-to-live-policy path, owner isolation, mood denominator preservation, source retrieval, permission withdrawal, contact binding, replay, cooldown and disabled switches. Existing public record counts were unchanged.
- 5 new suggestion UI checks passed with a synthetic DOM/API, including safe links and rejection of late results after logout.
- Existing AI/provider checks (49), real invitation checks (36), chat/support integration (32), chat frontend (29), support UI (13) and journal/mood frontend (25) passed during this work.
- Additive knowledge, live-email outbox and live-permission tables were created; existing consent-table restrictions and records were preserved.

Live invitation and automatic-alert switches remain OFF in the developer's private configuration. No real contact received an automatic email. New page visual review has not been completed after a previous browser-preview timeout. A full production deployment, real recipient journey and mobile test are not claimed.

## Documentation issues identified, not silently edited

The proposal mostly specifies PostgreSQL but section 3.8.4 says SQLite. The implementation uses PostgreSQL. Some proposal passages mention AI mental-health assessment, while the scope excludes clinical diagnosis/detection; documentation should describe non-diagnostic wellbeing support and the actual rule-based safety screen. The deployed model is Llama 3.2 3B, a member of the Llama 3 family. Do not describe its resource retrieval as embedding-based, clinically validated or full-document RAG.

## Immediate finish order

1. Review Home suggestions, source citations and contact-permission screens locally.
2. Choose and verify a public deployment with adequate resources for FastAPI, PostgreSQL and the Llama service. Private database/AI ports must stay unexposed. Hosting/domain choices may have costs; none were purchased.
3. Verify a real invitation/recipient decision/withdrawal journey, then one explicitly authorised live check-in email under supervision before wider use.
4. Complete actual mobile checks, student usability evaluation and Chapter 4 with the real evidence and limitations. SMS stays on hold until separately resumed.
