# ENWEN registration and database verification

Date: 2 November 2026

## Outcome

The current local FastAPI application and its PostgreSQL database passed the
checks below. No application-code or persistent database repair was needed.
This report is the only project file added during this verification session.
Existing uncommitted work was preserved. No Git commit or push was performed.

## Saved database records

Checked the database through the application's existing connection settings,
not through the pgAdmin user interface. Queries against existing tables were
read-only. Names, email addresses, passwords, tokens and journal contents were
not included in the diagnostic output or this report.

| Table | Saved rows before tests | Saved rows after tests |
| --- | ---: | ---: |
| users | 3 | 3 |
| consents | 4 | 4 |
| trusted_contacts | 1 | 1 |
| mood_entries | 10 | 10 |
| journal_entries | 3 | 3 |

- All five expected public tables exist. Their column names, types and nullability
  match the current Python models. Primary keys, foreign keys, uniqueness rules
  and check constraints were inspected.
- The newest account has a nonblank display name, an Argon2 password hash,
  one linked trusted contact and two consent records.
- The contact is pending and has both the wellness and contact-test consent
  records. Its email differs from the account email. No orphan contact was found.
- The two other accounts have no trusted-contact row; this verification did not
  create contacts or consent on their behalf.
- The application database role has no superuser, role-creation, database-creation,
  replication or row-security-bypass privileges. This is not a complete grant audit.
- The local environment file and virtual environment are Git-ignored; no tracked
  environment file, key or PEM file was found by the scoped filename check.
  This was not a full repository-history secret scan.

## Running application checks

Read-only requests were made to the existing server on http://127.0.0.1:8000.

| Check | Result |
| --- | --- |
| GET /health | 200; status ok |
| GET /health/db | 200; database connected |
| GET /auth/consent | 200 |
| GET /auth/contact-consent | 200; simulation_only |
| Home page, registration HTML, registration JS, stylesheet | Each returned 200 |
| GET /auth/me, /moods, /journals without a token | Each returned 401, as expected |

## Isolated integration tests

55 assertions passed using the current application routes and a real PostgreSQL
connection. These were in-process FastAPI TestClient requests, not authenticated
requests to the running browser session.

Tests used session-local TEMPORARY tables created from the current models. Every
test table and foreign-key target was verified as temporary. The test search path
excluded the public schema. Route sessions used savepoints inside an outer
transaction, which was rolled back at the end. No test accounts remained in the
public database, and the temporary tables were rolled back. No existing record
was deliberately inserted, updated or deleted.

Coverage included:

- Separate consent acceptance and notice-version checks.
- Rejection of self-contact email, short passwords and duplicate accounts.
- Successful registration with exactly one account, one pending contact and two
  consent records; Argon2 password verification; no sensitive input echoed in
  the checked validation response.
- Successful new-account login and profile retrieval; wrong passwords, invalid
  tokens and anonymous access rejected.
- Mood creation, history and out-of-range score rejection.
- Journal creation, reading, updating and deletion by its owner.
- Separation of mood histories and journal lists between accounts; another user
  could not read, update or delete a private journal by ID.
- No-store response headers on registration and login.
- Isolation safeguards and unchanged public record counts after testing.

The test runner emitted a non-blocking Starlette warning about its httpx test
client integration being deprecated. Tests passed; dependencies were not changed.
The diagnostic test program ran in memory and was not added to the repository.

## Scope and remaining work

- No live invitation or safety-alert emails were sent. The pending contact state
  is intentional, not an error. Do not mark it confirmed manually.
- Contact invitation, recipient acceptance/decline, live delivery, withdrawal
  handling and safety-alert workflows remain future work. Current notices permit
  fictional-data testing only; live email needs an updated permission flow.
- AI risk detection and emergency response were not implemented or validated.
  These checks do not establish clinical safety or production readiness.
- No browser interaction or real-account login was performed in this session.
  Page availability and current backend behaviour were tested separately.
- No database backup/restore or server restart was performed. Saved records were
  verified through fresh database connections; this report is not a data backup.
- Before deployment, review secrets, permissions, HTTPS, abuse protection,
  privacy controls, backups and recovery. Do not use real sensitive student data
  on the strength of these prototype checks alone.

Next milestone: prototype trusted-contact invitation and acceptance/decline in an
email sandbox, with explicit permissions, before considering live delivery.
