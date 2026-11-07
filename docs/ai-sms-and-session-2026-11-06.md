# Sessions, AI connection and SMS — 6 November 2026

Current state: local Ollama is selected and llama3.2:3b is installed. A real fictional exam-stress message received a local AI reply through ENWEN's browser chat. See local-llama-2026-11-06.md. The hosted-provider sections below are earlier checkpoints, not the active configuration. Cloud keys are unused by the local connector.

## Llama provider update

Budget update: the active OpenRouter pin is now meta-llama/llama-3.3-70b-instruct:free, with no paid fallback. The free webpage still advertises the model, but a neutral live test returned HTTP 404, "This model is unavailable for free". The authenticated catalog contained only paid Llama 3 entries. Therefore free hosted Llama access has NOT been demonstrated. No payment was made. Local Llama through Ollama remains an alternative to evaluate; it is not installed or connected yet. The non-free pin below describes the earlier checkpoint, not the active code.

The user's requirement is to retain Llama 3. A direct neutral test of Groq's llama-3.3-70b-versatile returned HTTP 404 / model_not_found. The Groq key authenticated successfully; it must not be reused with another service. OpenRouter currently lists Meta Llama 3.3 70B Instruct. The selected configuration is AI_PROVIDER=openrouter with a separate OPENROUTER_API_KEY. The model is pinned to meta-llama/llama-3.3-70b-instruct and no alternate model list is sent. Provider routing requests data_collection=deny; that setting is not a guarantee of confidentiality across all processors. The notice names OpenRouter and its model-hosting provider and uses a provider-specific version, so a prior Groq acknowledgement cannot authorise a different processor. Account credit/access and a real Llama reply still need verification.

The provider integration suite now passes 35 mocked AI/SMS checks. Existing Groq settings can remain in .env but are not used when OpenRouter is selected. No GPT or other substitute model was configured. Later sections describe the initial Groq checkpoint and remain as implementation history.

## Implemented

- Persistent login with an HttpOnly cookie, a database table storing only the saved-token hash, short-lived access tokens, automatic renewal, expiry and server-side logout revocation. HTTPS uses Secure cookies; local HTTP on loopback remains supported. The same website origin must serve frontend and backend.
- Session expires after seven days without renewal or 30 days from login, whichever comes first. It is deliberately not infinite. The additive initializer created browser_sessions on the local database without altering existing user data.
- Authenticated Let's talk page, explicit versioned acknowledgement before external AI processing, current wellness-consent check, bounded messages/history, per-user in-process request limits, cancellation and plain-text rendering. Messages remain in page memory; database chat history is unfinished.
- Groq API connector with timeout and bounded output. Keyword matching retrieves up to three public resource-catalog summaries; only these summaries and the submitted chat are sent. Existing journal/mood/account details are not sent. This is not an embedding index, full-article RAG, clinical validation or an AI risk classifier.
- Live Africa's Talking connection-test service and an interactive command that sends a single fixed neutral message to the developer's own configured phone. No chat, journal or contact data is included. Provider acceptance is not reported as confirmed handset delivery. Uncertain sends are not retried automatically.

## Configure privately

Add the settings from backend/.env.example to the END of the existing backend/.env. Keep existing DB_* and JWT_SECRET. Do not commit secrets or paste them into chat. The .env file is ignored by Git. Do not choose a model your provider account cannot access.

```
GROQ_API_KEY="your real key, stored locally only"
GROQ_MODEL="exact model ID available to your account"
AT_USERNAME="your live application username, not sandbox"
AT_API_KEY="your live application API key"
AT_SENDER_ID="sender authorised by the provider"
SMS_TEST_RECIPIENT="your own Kenyan mobile in +254 format"
SMS_MODE="live"
LIVE_SMS_ENABLED=true
```

Restart FastAPI after editing settings. Open the app, log in, refresh to verify persistence, and open Let's talk. With credentials absent, it clearly reports that the provider is not configured and does not fabricate a reply.

Only when ready to spend provider credit on ONE test to your own phone, run from backend:

```powershell
.\.venv\Scripts\python.exe send_sms_test.py
```

The command displays a masked destination and the exact neutral message, then requires typing SEND OWN TEST. Review both phone receipt and the provider dashboard. The agent has not run a live send.

## Remaining before contact alerts

Existing contacts contain email only, and existing invitation acceptance is a local test. Phone collection, ownership confirmation, separate live-alert permission, recipient agreement, withdrawal handling, duplicate prevention, delivery tracking, evaluated risk screening and an agreed human response process remain required work. None is silently enabled by the connection test. Do not describe this checkpoint as completed automatic escalation.

## Checks

- 18 backend persistent-session checks using PostgreSQL temporary tables; no real accounts modified.
- 5 frontend restoration checks including unavailable service and stale response after logout.
- 26 mocked AI/SMS checks, with no external AI calls or SMS sends.
- Existing contact backend suite: 85 checks, and existing frontend wellness/journal suite: 25 checks.
- Browser: demo login, refresh retained account, new chat page displayed missing-configuration state. Final logout/refresh and screenshot checks recorded during handoff.

No AI or SMS credentials were present at the initial configuration audit. External provider success, model suitability and real SMS delivery have not been demonstrated. All changes remain local and uncommitted.

## Official integration references

- https://console.groq.com/docs/api-reference
- https://console.groq.com/docs/quickstart
- https://help.africastalking.com/en/articles/2258472-how-do-i-start-sending-messages
- https://github.com/AfricasTalkingLtd/africastalking-python/blob/master/africastalking/SMS.py
