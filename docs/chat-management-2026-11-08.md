# Saved conversation controls — 8 November 2026

## Implemented and checked

Students can open a saved conversation and rename it through an inline, labelled editor, or deliberately delete it after confirming. Renaming preserves the transcript and unsent draft. Deletion removes the conversation, its saved user/AI messages, resource associations and conversation-level processing-notice snapshot from the active database. It preserves the unsent browser draft and keeps an already-visible human-support panel open. Pending message processing blocks deletion. This does not erase backups, separate student consent records or separate notification outcomes.

PATCH and DELETE /chat/conversations/{conversation_id} authenticate and check ownership on the server. Another owner's identifier and an unknown identifier both return 404. Names are bounded to 80 characters and rendered as plain text. Deletion is available through the API even after wellness-consent withdrawal, without requiring further AI processing. The main chat UI continues to require current consent to view history.

A new additive deleted_chat_requests table stores only owner UUID, request UUID and deletion time. claim_turn checks it before starting any generation or alert attempt. Replaying an old deleted request returns 410 rather than recreating messages or sending another notification. Concurrent claims and deletion use the same account lock; deletion locks turns before the conversation to match finalisation ordering. Notification records are separate and are not retracted by deleting chat text.

The additive initializer was run on the current database. Existing conversations were not deleted or renamed. Verification used rolled-back PostgreSQL TEMP tables and synthetic DOM/API data:

| Check group | Passed |
|---|---:|
| Rename, deletion, ownership, rollback and replay guards | 46 |
| Existing private history and support interruption | 52 |
| Integrated chat/support workflow | 26 |
| Frontend controller, including 14 new management cases | 29 |
| Public-only PWA cache policy | 11 |

Live browser inspection restored Demo Student login, opened the existing fictional `hi` thread and displayed its management controls and rename editor. No Save or Delete was submitted in that browser review. Evidence: ENWEN-tutorials/10-prototype-walkthrough/chat-management-2026-11-08.png, outside the repository. Automated endpoint tests performed actual rename/delete operations on temporary fictional records only. These checks are not clinical evaluation or user acceptance testing.

## Running locally

PostgreSQL must be running. From the project folder:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Keep that terminal open. Ollama must also be running with llama3.2:3b. Open http://127.0.0.1:8000/ instead of double-clicking HTML files. For local email captures, start Docker Desktop and the existing enwen-mailpit container; the inbox is http://127.0.0.1:8025/.

From the project root, a new read-only diagnostic can check the local services and required table names without reading student records or sending messages:

```powershell
.\backend\.venv\Scripts\python.exe tools/check_local.py
```

## External dependencies still pending

The developer confirmed on 8 November that no SMS provider account had been created. Africa's Talking signup/email verification, application creation, authorised sender and credit remain external setup tasks. Live trusted-contact alerts also need separate phone enrollment/verification, recipient agreement, fresh student live-alert permission and delivery tracking; the existing local email agreement does not satisfy those requirements. The own-phone connection-test script is not the automatic alert integration.

HTTPS deployment, actual phone installation, supervised safety evaluation and the approved rubric's remaining requirements are not completed by these changes. No numerical completion percentage is inferred.

Official SMS setup references checked 8 November:

- https://help.africastalking.com/en/articles/2258472-how-do-i-start-sending-messages
- https://help.africastalking.com/en/articles/11401519-how-do-i-verify-my-account
- https://help.africastalking.com/en/articles/407085-how-do-i-set-up-my-sender-id-in-kenya-or-uganda

Sender provisioning is provider-controlled and cannot be promised within today's deadline. Confirm current pricing/timelines in the provider dashboard before payment. No real SMS or paid provider interaction was performed.
