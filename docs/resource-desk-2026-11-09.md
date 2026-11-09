# Public resource desk checkpoint — 9 November 2026

## Delivered behaviour

The Resource Curator is a separate, operator-granted role. It can prepare new resources or revisions, inspect unpublished drafts, acknowledge a current source review, publish, retire and review the public-resource change history. It does not grant access to students' private journals, moods, chats, trusted contacts or bookmarks. A community moderator is not automatically a resource curator.

Open Resources → Open resource desk after signing in with an authorised account. Four views separate the library, draft editor, review queue and change history. An update starts from the existing public metadata; the original resource key stays fixed. Failed requests preserve the draft and retry identity. Logout clears the desk. Server-side permissions are rechecked for every protected request and write.

Publication requires a source checked on the current Nairobi date and acknowledgement of the versioned review notice. The publisher is derived from a permitted HTTPS source address; arbitrary hosts, embedded credentials and misleading Befrienders Facebook paths are rejected. This is an editorial link/source check, not clinical certification or evidence that a publisher recently reviewed its clinical content. The curator must check the final destination and source fidelity.

Drafts do not change the student library or AI retrieval. Publication changes the public resource and matching PostgreSQL knowledge summary in one transaction, with an immutable revision entry. Retrieval uses BM25 over curated public summaries, not embeddings or complete publisher articles. Retirement excludes the item from new library results and retrieval while retaining bookmarks, old chat citations and the revision history. Restoration needs a new reviewed draft. Concurrent edits, stale revisions, duplicate submissions and request replays are guarded.

The interface paginates library, draft and history views. The active corpus is limited to 1,000 sources. Each account can create at most 30 drafts per 24 hours. These are prototype limits, not a large-scale administration claim.

## Local setup and permission

The migration adds resource lifecycle columns without replacing existing metadata. `init_resource_admin.py` creates the role, draft and audit tables. `init_db.py` includes these tables for new installations. The insert-missing catalog initializer preserves existing reviewed or retired records.

The user explicitly approved the persistent local Resource Curator role for the existing Demo Student account. The operator applied it with `grant_resource_curator.py --email <account-email> --confirm`. The same command with `--revoke` removes it. There is no public role-grant endpoint and no automatically privileged seed account. Role assignments and database contents are not committed to Git.

## Verification completed

- 58 PostgreSQL TEMP-table backend checks: role separation/revocation, private-data boundaries, source validation, draft and publication retry behaviour, stale dates/revisions, atomic audit failure rollback, retirement/restoration, bookmark retention, knowledge sync and orphan-summary exclusion.
- 14 frontend checks: capability visibility, editor preservation, request identity, review/date gating, logout races and access revocation.
- 25 existing resource API checks, 37 functional-completion checks and 19 resource/breathing frontend checks passed. These total 153 focused checks; they are not clinical, user-acceptance or deployment evaluation.
- Live FastAPI/browser demonstration: a new NHS student-counselling draft remained absent from the library and knowledge index until publication. Acknowledged publication created revision 1, updated both public records and returned the new source in retrieval.
- A baseline comparison confirmed all original 13 resource snapshots and three existing bookmarks were unchanged. The local library now has 14 sources. No student journal, mood, chat or contact data was edited by this demonstration.
- The same public metadata was added to the insert-missing catalog for reproducible new installations. The source link was checked on 9 November; the publisher's displayed review date was March 2023. The audience note explicitly identifies UK service limitations for Kenyan readers. [NHS source](https://www.nhs.uk/mental-health/children-and-young-adults/help-for-teenagers-young-adults-and-students/student-mental-health-counselling/).

Local screenshot evidence is stored outside the public repository in `ENWEN-tutorials/10-prototype-walkthrough/resource-desk-history-2026-11-09.png`. The live role is local only. FastAPI remains available at `http://127.0.0.1:8000/`.

## Remaining scope

SMS remains on hold. Public HTTPS deployment, real-phone PWA installation, usability and safety evaluation, and final documentation are outstanding. The existing chat safety screen remains rule based and is not clinically validated risk classification. General user-account administration is separate from this resource role and has not been implemented. A completion percentage must be assessed against the final approved requirements and marking rubric.
