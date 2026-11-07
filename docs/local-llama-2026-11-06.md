# Local Llama integration — 6 November 2026

Superseded for chat storage and safety behaviour by safety-history-2026-11-07.md: chat history is now saved with a new acknowledgement, support interruption is implemented, and local Mailpit notification capture has been demonstrated. Local Llama remains the selected model. The no-history descriptions below record the earlier 6 November checkpoint.

## Current configuration

ENWEN now selects AI_PROVIDER=ollama. Inference calls go only to http://127.0.0.1:11434/api/chat, with no cloud credentials or cloud fallback. Meta Llama 3.2 3B (llama3.2:3b) was downloaded from the official Ollama registry and its digest verified by Ollama. This is a Llama 3-family model, not the hosted 70B variant attempted earlier. The smaller 2 GB model was selected because this computer has about 8 GB installed memory. No per-message AI API fee is involved in local inference; downloading the model uses internet data.

The backend builds a system instruction plus up to three relevant public catalog summaries, matched by keywords, and the submitted conversation. It does not retrieve saved journals, moods or user account details for the prompt. Catalog summaries are not full articles, an embedding index, clinical approval or an evaluated medical knowledge base. The assistant is non-diagnostic and cannot contact anyone.

Local generation is limited to one request at a time, a 4,096-token context setting, 256 generated tokens, at most 6,000 conversation characters and a 120-second backend timeout. The browser allows 150 seconds and preserves the draft on failure. These limits control this laptop's memory use and response time; output can end at the generation limit. Responses are rendered as text. Sources are shown separately as server-provided HTTPS links.

## Consent and data handling

The processing notice and checkbox identify local Ollama. Earlier acknowledgements for Groq/OpenRouter cannot authorise this provider because the notice version includes the provider ID. The existing request field external_ai_consent is retained for compatibility; on this route it records acknowledgement of the displayed LOCAL processing notice, not permission to transmit externally. No chat transcript or durable chat-consent record is saved in the database yet. Messages remain in page memory and clear on refresh/logout. Do not claim database chat history or completed clinical safety evaluation.

## Running and demonstration

1. Open Ollama from the Windows Start menu. Keep it running locally. Do not expose its port to the network.
2. Keep PostgreSQL and ENWEN's FastAPI server running. Mailpit is only needed for email demonstrations.
3. Open http://127.0.0.1:8000/#/chat and log in. Read the local-processing notice and tick the acknowledgement.
4. Use a fictional student-life prompt, for example: "For this fictional demonstration, I feel overwhelmed by exams. Help me choose one small next step."
5. Wait for the AI reply. The first reply may take longer while the model loads. Do not repeatedly click Send.

To inspect installed models in a new PowerShell terminal:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

The installed command might not appear on PATH in an older VS Code terminal; the full path above avoids that issue. Existing provider keys can remain in the ignored .env file but are unused by the local route. AI_PROVIDER is already set to ollama; no new account/key is required.

## Verification

- 49 mocked AI/SMS integration checks pass, including local response parsing, missing-model reporting, local-only endpoint, no cloud headers, consent version, bounded context, rejecting incomplete replies and limiting parallel local generations.
- Persistent-session frontend checks continue to pass.
- Ollama's model list confirms llama3.2:3b, 2,019,393,189 bytes.
- Live browser test passed: the actual Let's talk form submitted a fictional exam-stress request, received a real response from local Llama and displayed the NHS student-stress summary source. Screenshot: ENWEN-tutorials/10-prototype-walkthrough/local-llama-live-2026-11-06.png (outside the repository). This demonstrates connectivity, not clinical effectiveness or completed safety evaluation.
- No real SMS was sent. Automatic risk detection, verified trusted-contact phone collection, live alert consent, escalation and delivery tracking remain unfinished. Saved chat history and clinical/user evaluation are also unfinished.

## Official references

- https://ollama.com/library/llama3.2:3b
- https://docs.ollama.com/api/chat
- https://docs.ollama.com/faq
