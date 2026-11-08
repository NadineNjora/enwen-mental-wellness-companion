# Student-context and mood-insight checkpoint — 8 November 2026

This implements the supervisor's request to make check-ins more student-oriented and show when students check in and what was part of their day.

## Behaviour

- A student can select up to six of twelve factors, including coursework, exams, finances, relationships, family, sleep, health, commute, weather, feeling disconnected, special occasions and rest.
- Existing writing prompts still append to the note without replacing the student's words. Choosing a starting prompt also selects its matching factor when capacity allows. Tags remain independently editable in the factor panel.
- Mood score, note and factors are saved in one database transaction. Failed saves keep the form draft. History restores the saved factors alongside the original note and timestamp.
- The private history summary offers 7, 30 and 90 day calendar windows. It counts recorded check-ins, distinct days, student-chosen factors, unlabelled entries, weekdays and time bands in Nairobi (UTC+03:00). Future timestamps and records outside the selected period are excluded.
- Recorded averages are reported separately for the original 1–5 and current 1–10 scales. Existing scores are never rewritten or combined into a new scale.
- Factors describe selections alongside check-ins. They do not establish causes, diagnoses or the student's mood between entries. Multiple entries on one day each count. Untagged old notes remain untagged; their contents are not sent to AI or retrospectively analysed.

## Database and API

The additive mood_contexts table references mood_entries and stores a validated factor key per entry. Existing account, contact, journal, chat, mood and consent records are preserved. backend/init_db.py includes the new table for future installations; running it again creates missing tables without deleting records.

POST /moods accepts a contexts list; older compatible clients may omit it. GET /moods returns the saved factors. GET /moods/context-options provides the factor choices. GET /moods/insights accepts days=7, 30 or 90. All require login and current wellness consent. Responses use no-store; summaries include only the current owner's data and exclude private note contents. Logout clears the new screen and rejects late responses from earlier sessions.

## Verification

- 29 temporary-database context/insight checks passed: valid and invalid factors, atomic writes, owner isolation, consent, calendar windows, Nairobi time bands, separate legacy averages, no note disclosure and unchanged public records.
- 36 existing mood API checks passed against temporary tables.
- 12 new interface checks passed: factor limit, deselection, separate averages, empty/failed states, draft preservation and late-response/logout protection.
- 26 existing journal/mood frontend checks and 12 prompt-helper checks passed, including a new actual-form failure case preserving the factor/note draft.

These 115 checks use temporary or synthetic data. They do not establish a grade, a completion percentage, clinical validity or student usability approval.

The running browser was also verified after restarting FastAPI. One clearly labelled fictional check-in was saved to Demo Student with 7/10, Coursework and Rest factors. The saved form cleared, the factors appeared on the dated history entry and in the new summary, and the original complete-history chart remained visible. Separate 1–10 and legacy 1–5 averages were displayed. The 7-day and 90-day controls were exercised, then the view was restored to 30 days. A local screenshot was saved outside the Git repository as student-context-history-2026-11-08.png. Existing records were retained; this single fictional demonstration entry was deliberately added, rather than representing a real student's mood.

## Remaining work

Public HTTPS deployment, real-device PWA testing, supervised quality/safety evaluation, student usability evaluation and final documentation remain. Peer journaling and community moderation were added in the subsequent [community checkpoint](community-checkpoint-2026-11-08.md); full user/resource administration remains outstanding. SMS remains on hold. The local email demonstration is verified in the separate delivery checkpoint; broader real-contact operation is not claimed.
