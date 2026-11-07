# Two-screen registration — 4 November 2026

## Completed

Registration now presents two screens within the same page:

1. Account details and the existing wellness-consent notice.
2. Trusted-person details and the existing contact-testing notice.

Nothing is saved by Continue or Back. Only **Create my account** on screen 2 sends the complete payload to the existing registration endpoint, which saves the user, both consent records, and pending contact together. No invitation is sent during registration.

The coral/lilac/cream theme is retained in a compact joined layout with paired desktop fields, a flower illustration, progress indicators, and single-column styles for smaller screens. Existing notice wording is fetched unchanged from the backend. Back and Edit retain the current form values. Passwords stay only in browser memory and are cleared after a submission attempt or a restored browser page.

The registration HTML is served with `Cache-Control: no-store`, and the signup link and page assets have versioned URLs, to reduce stale-layout problems. No database migration or dependency change was needed.

## Verification performed

- 12 new frontend registration scenarios passed with a simulated DOM/API: step boundaries, validation, Back/Edit preservation, duplicate-submit protection, success, existing email, failed save, changed notices, unavailable notices, and browser restore.
- The existing contact-dashboard (11) and response-page (7) frontend scenarios also passed: 30 frontend scenarios total.
- The isolated PostgreSQL backend suite passed 71 checks, including nine added registration checks for the complete payload, user/contact/consent creation, duplicate rejection, required contact permission, and no partial records on failure. Temporary test tables were rolled back; public row counts were unchanged. The suite used a fake mail sender.
- Actual browser checks confirmed screen 1, Continue to screen 2, and Back with preserved unsaved fictional data. The final Create action was not performed against the user's saved database in the browser. Unsaved browser test entries were cleared afterwards.
- Registration HTML/CSS/JS served successfully, the HTML returned `no-store`, and `/health/db` returned `connected`.
- JavaScript syntax and `git diff --check` passed. Browser visual inspection used the default desktop viewport; smaller-screen CSS is included, but a phone/device preview was not run.

## Your manual acceptance check

1. Open http://127.0.0.1:8000/static/register.html?v=20261104-two-steps.
2. Use a new fictional account email, a preferred name, and a test password of 12–128 characters. Read and accept the wellness notice, then Continue.
3. On screen 2, enter a fictional contact with a different `@example.com` email. Try Back once to check the account details remain, then Continue again.
4. Read and accept the contact-testing notice, then create the account. The success screen should offer Continue to log in.
5. Log in and check Trusted contact. The new contact should be pending / Invitation not sent.

Do not use real health details or real contacts during these tests. Do not post credentials, tokens, `.env`, or invitation links in screenshots or on GitHub. Live email and safety alerts remain disabled.

## Next checkpoint

After the manual check, review and commit the appropriate source, tests and documentation, then push to GitHub. This work is saved locally only; no commit or push was performed in this task. Save screenshots without credentials as Chapter 4 evidence. Further features should be selected against the approved requirements rather than assigning an unverified completion percentage.
