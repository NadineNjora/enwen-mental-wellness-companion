# Resource library and grounding prototype

Completed 5 November 2026.

## Functional additions

Resources is a separate screen with search, topic filtering, original-publisher
links and Saved by me. The signed-in student's bookmarks are stored in PostgreSQL.
The read-only catalog has five initial entries; source checking is distinct from
supervisor or clinical approval, neither of which is represented as completed.

Take a pause is a separate screen with optional grounding prompts and a one-minute
browser timer. Start, Pause, Continue and Reset work; navigation away, hiding the
tab and logout stop the timer. The countdown uses elapsed time rather than counting
interval callbacks. It does not assess mood or measure wellbeing.

Dashboard cards and navigation connect both screens to the existing account flow.
Login and current consent gate the new features. An expired session clears resource
state. Requests from an earlier login cannot update a later account's screen.

## Data and API

Two new tables were added: wellness_resources and resource_bookmarks. A bookmark's
composite primary key is user_id plus resource_id; both are foreign keys. Removing
a bookmark does not delete the catalog item. Existing student records were preserved.

- GET /resources accepts q, category and saved_only.
- PUT /resources/{resource_id}/bookmark saves idempotently.
- DELETE /resources/{resource_id}/bookmark removes only the current user's bookmark.
- All responses use no-store. Save/read require current wellness consent; removal
  remains available to the authenticated owner even if that consent is no longer current.

Run init_resources.py using the backend virtual environment to create and seed
these new tables. init_db.py also calls this setup. It inserts missing catalog IDs
and preserves existing rows. Re-running was verified to add zero duplicate entries.
No new dependencies, real emails or AI service calls were introduced.

## Verification

- 25 resource API checks passed using real PostgreSQL TEMP tables rolled back at
  the end. Coverage includes auth/consent, search, category filtering, literal
  wildcard handling, bookmark persistence/idempotency and account separation.
- 18 synthetic frontend/timer scenarios passed, covering failed requests, stale
  responses, unsafe URL rejection, empty results, save/remove states and timer behaviour.
- Existing regressions passed: 73 registration/contact backend checks, 36 mood API
  checks, 24 journal/mood frontend scenarios, 12 registration scenarios, 11 contact
  dashboard scenarios, 7 contact-response scenarios and 12 prompt-helper scenarios.
- Browser verified: login to Resources; five publisher cards; Rest & sleep filter;
  save a reading; retrieve it through Saved by me; remove that newly created test
  bookmark to restore the demo account's prior state. No moods or journals were changed.
- Browser verified Start and full completion of a minute, then a second run paused
  at 45 seconds and reset. The normal 15-minute login expiry also cleared the UI.
- JavaScript syntax, git diff --check, app health, database health and new asset
  HTTP checks passed. Visual checks used the desktop viewport; mobile was not previewed.
- The existing upstream Starlette test-client deprecation warning remains non-blocking.

## Source provenance

The catalog links to the original publishers rather than reproducing their texts:

- WHO Doing What Matters in Times of Stress: https://www.who.int/publications/i/item/9789240003927
- NHS student stress: https://www.nhs.uk/mental-health/children-and-young-adults/help-for-teenagers-young-adults-and-students/student-stress-self-help-tips/
- NHS sleep reading: https://www.nhs.uk/every-mind-matters/mental-wellbeing-tips/how-to-fall-asleep-faster-and-sleep-better/
- NHS loneliness: https://www.nhs.uk/every-mind-matters/lifes-challenges/loneliness/
- University of Nairobi counselling: https://studentlife.uonbi.ac.ke/student-services/guidance-and-counseling-section

Publisher content/search results were checked while preparing the catalog. A direct
fetch of the University of Nairobi page timed out; its original-domain search result
provided the counselling-service description. External site availability is outside
ENWEN's control. NHS service instructions apply to the UK; university eligibility
depends on the named institution. These distinctions appear on the relevant cards.

## Handoff

The student walkthrough and screenshots are outside the repository in
ENWEN-tutorials/10-prototype-walkthrough. All changes remain local and uncommitted.
AI/RAG, formal resource approval/admin, live escalation, peer sharing, PWA installation
and deployment remain separate milestones. No academic completion percentage has
been verified against a supervisor's marking checklist.
