# ENWEN Mental Wellness Companion

ENWEN is a web-based, non-diagnostic mental-wellness companion for Kenyan university students. The planned system combines secure mood tracking, private journaling, emotional trend visualization, approved wellness resources, and a Llama 3 conversational assistant grounded through retrieval-augmented generation (RAG).

## Project status

**Current checkpoint, 8 November:** Student-selected factors now save alongside mood check-ins, with private 7/30/90-day summaries of recorded averages, factors, weekdays and check-in times in Nairobi. Original 1–5 and 1–10 scores stay separate; existing notes are preserved. See [the student-context checkpoint](docs/student-context-2026-11-08.md). The restricted local real-email invitation → accepted contact → separate student permission → interrupted fictional chat → labelled check-in email journey has also been verified, and the user confirmed inbox receipt. SMS remains on hold; public deployment and mobile/user evaluation remain outstanding. See [the verified email demonstration](docs/local-email-presentation-2026-11-08.md). Earlier paragraphs below describe historical checkpoints.

**Functional checkpoint, 8 November:** Added personalised Home suggestions from the owner's latest check-in, BM25 retrieval over attributed PostgreSQL knowledge summaries, and a separate live-email check-in policy/outbox with contact-bound permission, recipient agreement, demonstration suppression and duplicate protection. Automated live delivery remains OFF pending public deployment and authorised end-to-end verification. SMS is on hold. See [the proposal-to-implementation checklist and finish order](docs/functional-completion-2026-11-08.md). Deployment/backup files remain supporting drafts, not completed student functionality.

**Real email enrollment, 8 November:** Added separate live invitations with explicit student permission, recipient Accept/Decline and withdrawal, hashed expiring response links and durable duplicate-send protection. Own-mailbox email delivery was confirmed by the developer. Real invitations remain disabled pending public HTTPS deployment; automatic safety alerts and live SMS are not enabled. See [the enrollment checkpoint, tests and deployment dependency](docs/real-invitations-2026-11-08.md).

**Brevo SMS option, 8 November:** Brevo is now selectable for the own-phone SMS connection test as well as the existing email test. Only the provider account has been created; sender approval, credits and live configuration are not confirmed. Existing Mailpit mail remains local. See [Brevo verification and configuration steps](docs/brevo-email-sms-2026-11-08.md).

**Delivery options and screen coverage, 8 November:** Added Twilio as a selectable own-phone SMS test connector and a separate Brevo own-mailbox email test. Live sending remains disabled; existing Mailpit invitations are not redirected to real recipients. Added explicit phrase examples to the rule-based support screen and verified that flagged requests bypass ordinary AI replies. These are not automatic live alerts or validated risk detection. See [provider setup, test evidence and remaining delivery work](docs/delivery-options-2026-11-08.md).

**Saved-chat controls, 8 November:** Students can rename and deliberately remove a saved conversation, with ownership checks, draft preservation and content-free replay protection. Deleting a transcript keeps separate notification outcomes and any visible support mode intact. Existing conversations were preserved during verification. See [the management checkpoint and local run instructions](docs/chat-management-2026-11-08.md). Run `backend/.venv/Scripts/python.exe tools/check_local.py` from the project root for a read-only service/schema check; it does not send messages or read student records.

**PWA preparation, 7 November:** Added an installation manifest, public flower icons, browser installation guidance and a public-only offline fallback. Private records and submitted requests are never cached or queued by the worker. Phone installation still needs a reachable HTTPS deployment and real-device testing; backend/Ollama remain on this computer. See [the PWA checkpoint and limits](docs/pwa-checkpoint-2026-11-07.md).

**7 November checkpoint:** Private chat history now saves acknowledged conversations and restores them after refresh. A prototype action-language safety screen interrupts ordinary Llama replies and displays verified Kenyan human-support contacts. A local-only notification outbox records capture/blocked/uncertain outcomes, suppresses duplicate requests and applies a cooldown. The live browser safety/history demonstration and one fixed synthetic Mailpit capture passed. This is not clinically validated risk prediction or live SMS escalation. See [the current safety/history checkpoint](docs/safety-history-2026-11-07.md). Earlier dated paragraphs below describe previous checkpoints.

Local academic prototype. Implemented: registration with separate consent records and fictional trusted-contact details, JWT login, personalized navigation, mood check-ins/history with a graph, and private journal CRUD in the frontend and backend. Optional student-context and journal-reflection prompts preserve existing drafts and save through the existing forms.

The resource library contains 13 source-linked readings and provider pages, with topic/search filters and private saved links. A mindful-minute screen offers a breathing flower with four 4–4–4–4 rounds, affirmations, reduced-motion support and a separate five-senses grounding garden. Older accounts can now add a trusted person with explicit consent. New resource tables are created and seeded by `backend/init_resources.py`, also called by `init_db.py`. Re-running the resource initializer inserts only missing catalog items. Source verification is separate from supervisor or clinical approval; no such approval is claimed.

As of 3 November 2026, trusted-contact test invitations are connected to the app. The home dashboard shows contact status, and a separate Trusted contact screen supports sending local invitations, checking status, and replacing pending invitations. Contacts can accept or decline through an expiring, single-use link. Email is captured in local Mailpit only; no real email delivery or automated safety alerts are enabled.

The 6 November update adds persistent browser login and an authenticated local Llama chat screen. AI_PROVIDER=ollama connects only to 127.0.0.1:11434, pinned to Meta Llama 3.2 3B (llama3.2:3b), a smaller member of the Llama 3 family. The 2 GB model is installed on this computer. Groq could not serve the requested Llama and OpenRouter's advertised free route was unavailable; those adapters remain unused. No cloud fallback is enabled. Keyword matching retrieves public catalog summaries for the prompt; this is not full-document or embedding-based RAG. The local connector has passed mocked integration checks; the live browser demonstration is recorded in docs/local-llama-2026-11-06.md. Chat messages are not saved to the database. Formal resource approval, administration, evaluated risk screening, live escalation, peer journals, PWA installation and deployment remain future work. Student context currently saves as free-text notes; structured context analytics are not implemented. This checkpoint is not a claim that a particular percentage of the academic requirements is complete.

Saved login uses an HttpOnly, SameSite=Strict cookie and database-backed revocation. Access tokens last 15 minutes and renew in the browser. The saved session lasts seven days between renewals, with a maximum of 30 days before reauthentication. Logout revokes the saved session and its access tokens. No access or session tokens are stored in localStorage. On an existing database run `backend/init_sessions.py` once with the backend virtual environment; it only creates the new session table. This was run on the current local database.

`backend/sms_service.py` and `backend/send_sms_test.py` support a deliberate LIVE Africa's Talking connection test to the developer's own configured phone. They are not connected to chat or existing trusted contacts. Provider credentials, an authorised sender and credit are required. See `docs/ai-sms-and-session-2026-11-06.md`. No live SMS was sent during development checks.

See [the contact-flow checkpoint and run guide](docs/contact-flow-checkpoint-2026-11-03.md) for setup, tests, limitations, and the manual demonstration.

Registration now uses a compact two-screen flow: account first, trusted person second, with one final save. See [the 4 November registration redesign and verification notes](docs/registration-redesign-2026-11-04.md).

New mood check-ins use a 1–10 scale with emojis. Earlier 1–5 records retain their original values and scale. History loads all saved entries and shows both scales in separate panels over a shared timeline; the dated list is paginated. On an existing database, run `backend/migrate_mood_scale.py` with the backend virtual environment before starting this version. For new databases, `init_db.py` creates the updated schema. See [the scale migration and typography notes](docs/mood-scale-and-typography-2026-11-04.md).

## Planned architecture

- Frontend: HTML, CSS, and JavaScript
- Backend API: Python and FastAPI
- Database: PostgreSQL
- AI: Llama 3 with RAG over approved wellness resources
- Testing: Pytest, integration tests, safety evaluation, and user acceptance testing

## Core modules

1. User registration, authentication, profile, and informed consent
2. Daily mood recording and emotional trend visualization
3. Private journal entry management
4. Approved wellness-resource library
5. AI wellness conversations and grounded recommendations
6. Safety screening and professional-help referral flow
7. Administration of users and approved resources

## Safety boundary

ENWEN is intended for wellness support and self-reflection. It must not diagnose mental-health conditions or replace qualified professional care. Crisis and severe-distress language must lead to a safe response and an appropriate professional-help referral.

## Repository layout

```text
backend/     FastAPI application
frontend/    Browser-based user interface
docs/        Requirements, architecture, diagrams, and research documentation
tests/       Isolated backend and frontend regression checks
```

## Development roadmap

- Phase 1: Repository, requirements, database design, and development environment
- Phase 2: Authentication, consent, profiles, mood tracking, and journaling
- Phase 3: Wellness resources, Llama 3, RAG, and chat persistence
- Phase 4: Safety controls, testing, evaluation, deployment, and documentation



