# Trusted-contact checkpoint — 3 November 2026

## Completed

- Preserved the user's `contacts_invitations.py` and `contacts_response.html` filenames. The latter was empty and is now a complete response page.
- Connected the invitation router in `backend/main.py`; invitation email links now match the actual page. Earlier `/static/contact-response.html` tutorial links also work through a compatibility route.
- Added home-dashboard contact status, a dedicated Trusted contact route, and contact details with Refresh status.
- Added an explicit test notice and acknowledgement before sending; displayed invitation expiry, server-enforced cooldown, and a warning before replacing a pending link.
- Disabled invitations for accepted, declined, revoked, or ineligible contacts. Older accounts with no contact get a clear explanation without altering their data.
- Reset contact details and pending browser requests on logout; stale responses cannot repopulate a later session. Uncertain sends are not automatically retried.
- Preserved the existing wording and styling of the login, mood and journal screens. The local Sites workflow was used to keep new UI consistent and avoid publishing the app.

## Run the app

In PowerShell:

```powershell
cd "C:\Users\admin\Desktop\IS PROJECT\enwen-mental-wellness-companion\backend"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Use http://127.0.0.1:8000/ for the frontend and http://127.0.0.1:8000/docs for API documentation. FastAPI serves both the frontend and backend; do not open an HTML file with `file://`. If port 8000 is already serving ENWEN, use that instance rather than starting another.

Mailpit's inbox is http://127.0.0.1:8025/; the existing local SMTP receiver uses port 1025. Delivery remains hard-coded to this computer and restricted to fictional `@example.com` recipients.

## Demonstrate the flow

1. Log in to a fictional account created with a pending trusted contact using `@example.com`.
2. Open **Trusted contact** in the navigation or use the dashboard card.
3. Read the local-test notice and tick its acknowledgement. Choose **Send test invitation** once.
4. Open Mailpit on this computer and open the newest invitation's complete link.
5. Read the response notice, tick the test acknowledgement, then choose Accept or Decline. Merely opening the page does not decide anything.
6. Return to ENWEN and choose **Refresh status**. The screen should show **Accepted · test only** or **Declined · test only**, and the send form should disappear.

Each link lasts 24 hours and is single-use. A successful replacement invalidates the previous unused link. The server enforces at least 60 seconds between requests. A failed send leaves the previous valid invitation intact. Refreshing the response page requires reopening the original complete link because its secret is removed from the address bar and held only in memory.

Do not manually edit database rows to test the opposite decision. Use a separate fictional account. No user's existing contact was accepted, declined or replaced by the automated checks.

## Verification

Run from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -B tests\test_contact_backend.py
node tests/test_contact_response.cjs
node tests/test_contact_dashboard.cjs
```

The backend test requires the existing local PostgreSQL database and configured backend `.env`. It creates temporary tables on one connection, uses a fake email sender, rolls the tables back, and confirms public row counts are unchanged. Never redirect it to a production database.

Results at this checkpoint:

- 62 backend checks passed, including authorization, ownership isolation, expiry, single use, declined contacts, withdrawn consent, cooldown, and rollback after email failure.
- 7 response-page scenarios and 11 dashboard scenarios passed using simulated browser requests.
- Browser QA used the actual frontend files with an isolated in-memory preview: login, contact navigation, explicit send, acceptance, status refresh, and journal navigation worked. No saved accounts or email messages were changed by that preview.
- The running app's database health returned `connected`; Mailpit's inbox was reachable.

This is layered verification, not a claim that the live database and Mailpit were exercised together with a real person's contact. Complete the manual demonstration using fictional data before presenting. The backend test currently emits an upstream TestClient deprecation warning; it passes without changing installed dependencies.

## Safety boundaries and remaining work

`confirmed` is only a local demo decision, not verified mailbox ownership or authorization for real safety alerts. No moods or journals are included in invitations. There is no AI risk detection or emergency response in this flow.

Before live delivery: design and review fresh consent, recipient verification, withdrawal/revocation, secure deployment URLs, durable email delivery and retry tracking, rate limits, and human escalation procedures. Do not convert this demo's accepted statuses into live permission.

The account's earlier storage-only consent notice remains unchanged. A separate current local-test notice is acknowledged when an invitation is sent. The invitation notice version is checked but a full historical invitation-notice audit is not yet stored; production use needs that audit design.

Existing behavior remains: browser refresh logs users out and access tokens expire after 15 minutes. Older accounts without contacts need a future contact-management flow; current guidance is to use a new fictional registration, not overwrite their saved records.

## Saved work and Git

Application changes and tests are saved locally. No commit or public push was made for this checkpoint. Existing changes to `init_db.py`, the invitation model and mail helper were preserved. `.env` remains ignored. Before pushing, review the diff and explicitly select project source, tests, and documentation; never commit `.env`, credentials, database exports, or captured invitation links.
