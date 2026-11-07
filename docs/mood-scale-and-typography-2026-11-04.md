# Ten-point mood scale and typography

Date: 4 November 2026

## Implemented

- New mood check-ins offer ten numbered choices, each with a written label and
  emoji. Keyboard-accessible radio inputs retain native form validation.
- The API requires an integer mood_score from 1 to 10 and an explicit scale_max
  of 10. An old 1–5 form that omits this field is rejected rather than silently
  treating its answer as a 1–10 score.
- Database constraints validate the score against each record's original scale.
  The migration added scale_max=5 to the existing 16 records without changing
  their scores, notes, account links, IDs or timestamps. A fingerprint over those
  original fields matched before and after the migration.
- Earlier entries remain labelled out of 5. The graph plots only new 1–10 records
  among the latest 20 check-ins. An explanatory empty state is shown until a new
  score exists. No rescaling or inference about earlier moods was performed.
- The application uses Georgia for headings, Candara for body text, Bahnschrift
  for labels/navigation and Segoe Print for optional prompts, with fallback font
  families. No external font service is contacted. The exact fonts can vary on
  devices that do not have these fonts installed.
- Typography applies to the main app, registration and invitation response page.
  New emojis were added to mood choices, selected headings and prompt buttons.
  Existing written prompts and journal content were preserved.

## Database setup and API example

For an existing database, from backend run the migration before this version:

```powershell
.\.venv\Scripts\python.exe migrate_mood_scale.py
```

It is transactional, uses short lock/statement timeouts and can be re-run. Its
default remains 5 for legacy writers during rollout; the new API always supplies
10 explicitly. For a new database, init_db.py creates the new model schema.
Changing models.py or running create_all alone does not migrate an old table.

Example POST /moods payload, after login and consent:

```json
{"mood_score": 8, "scale_max": 10, "note": "Fictional test: a calm study break."}
```

## Verification

- Nine real-PostgreSQL temporary-table migration checks passed, including repeat
  execution, unchanged legacy values, valid new boundaries, invalid data rejection
  and preserving the original meaning of writes from old application processes.
- Thirty-six mood API checks passed using temporary tables and synthetic accounts.
  These cover scores 1–10, invalid/stale requests, scale metadata, ownership filters,
  consent, no-store responses and unchanged public data after tests.
- Seventy-one existing registration/contact backend checks passed. A usage-limit
  failure initially blocked this run; the retry after reset succeeded.
- Twenty-four journal/mood frontend scenarios, twelve prompt-helper scenarios and
  thirty registration/contact frontend scenarios passed with a synthetic DOM/API.
- The upstream Starlette test-client deprecation warning remains non-blocking;
  no dependency versions were changed.
- A fresh browser tab displayed all ten choices, emoji labels, the font mix and
  journal prompts. Computed styles confirmed all four font roles. Existing demo
  account history showed the earlier 1–5 labels and the new graph's empty state.
- No new public check-ins or journals were created by these checks. New 1–10 save
  behaviour was tested against the real database engine using rolled-back temporary
  tables, rather than adding sample moods to the user's account.
- Visual inspection used the desktop viewport. No phone/device preview was run.

## User acceptance and evidence

Refresh the running page with Ctrl+F5, log in, save two fictional check-ins on the
new scale and verify their graph and history. Confirm journal create/read/edit/
delete and the local invitation demonstration before the supervisor meeting.

Screenshots and two preparation guides are stored outside the repository under
ENWEN-tutorials/09-review-and-resource-preparation. The guides cover Chapter 4
evidence and candidate resources for the future approved library and AI retrieval.

These changes are saved locally. No Git commit or push was performed. AI/RAG,
live escalation and deployment remain outstanding; this update does not establish
an academic completion percentage or clinical validity for the mood scale.
