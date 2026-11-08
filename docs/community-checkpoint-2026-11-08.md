# Peer reflections and community moderation — 8 November 2026

## Implemented behaviour

Community is a separate screen with Read together, Share a reflection, My sharing and a role-restricted Moderation view. Students deliberately write a new community submission; private journals are never copied, linked or automatically shared. Each post and each response requires the current sharing notice and a separate explicit acknowledgement.

Published content uses a generic peer label. Names, emails, account IDs and submission identifiers are omitted from the feed. This is pseudonymous sharing: the database retains ownership internally, and deliberately submitted content is visible to moderators. Student affiliation is not independently verified by this prototype. The notice asks authors to omit identifying details and web links.

Every reflection and response starts in a review queue. The existing non-clinical rule screen holds explicit danger language, and a basic pattern check holds likely contact details or links. These checks can miss content or over-trigger; they are not AI moderation, clinical assessment or a guarantee of privacy. Flagged items cannot be approved into the feed. Suitable unflagged content can be published by a different moderator after acknowledging a review checklist. No self-approval is permitted.

Readers can report published posts and feedback. Reports are deduplicated per reporter and item and prioritised in moderation. Reporting does not immediately remove content and is not an emergency alert. A moderator can decline a pending item or remove an approved item from the feed. Stale decisions are rejected using a revision check; review decisions produce a separate content-free audit record.

Authors can withdraw their own sharing, including after withdrawing wellness consent. Withdrawal removes a post and its responses from shared reading; submitted content and review history are retained as disclosed in the sharing notice. Previously published text is immutable; corrections require withdrawing and deliberately submitting a fresh item for review.

## Access and delivery

Ordinary users cannot access the moderation queue or change roles. Moderator access is an explicit database-backed role, assigned by the local operator using grant_community_moderator.py --email ACCOUNT --confirm; --revoke removes it. No web role-grant endpoint, default moderator password or email-domain auto-promotion exists. This role only reviews submitted community content and reports. It does not add access to private journals, moods, chats or contact records.

All community endpoints require login. Reading and new sharing also require current wellness consent. Responses use no-store; no browser storage or offline queue holds shared drafts or API results. Logout clears private screen state and late responses are ignored. Failed sharing keeps the draft and its request ID. Durable unique request IDs prevent repeated posts/responses; daily limits are 10 posts, 20 responses and 30 reports per account. The queue shows a bounded batch of 20 items from up to 50 candidate posts and 50 candidate responses; reviewers refresh after decisions.

Community submission does not call the Llama model, index content for retrieval, send a trusted-contact email or send SMS. The separately consented chat-to-contact pathway remains separate. Moderation is not continuously monitored and is not an emergency service.

## Database and verification

The additive community_moderators, community_posts, community_feedback, community_reports and community_reviews tables are included in init_db.py. init_community.py creates only these missing tables. Existing private journals and other records are preserved.

59 temporary-database checks cover sharing agreement, owner isolation, no automatic journal sharing, pseudonymous DTOs, pending-only visibility, self-review prevention, role checks and immediate revocation, approval, response review, report deduplication, stale decisions, privacy/support holds, withdrawal and quotas. 15 new interface checks cover explicit acknowledgement, full draft preservation, retry identity, safe text rendering, role visibility, checklist gating, unsafe decision reasons and logout/late-response protection. Existing journal/mood (26) and insight (12) UI regression checks also passed: 112 focused checks in total. All database tests use TEMP tables and roll back; they send no email or SMS and make no AI calls.

## Local demonstration

The user explicitly authorised assigning Demo Student the persistent community-only moderator role. The role was assigned by the operator CLI; existing account credentials and private-data access rules were unchanged. Two fictional ordinary accounts were created through the local registration API, with fictional contacts and test notices, to exercise sharing between different users. Generated temporary passwords were held only in an ignored local fixture record and removed from that record after the submissions were created. No additional moderator role was assigned.

One clearly labelled fictional reflection was submitted, reviewed and approved through the running moderation screen, then verified in the signed-in feed. One clearly labelled fictional peer response was submitted for review. Its recorded review outcome was rejection; that decision was preserved and it remained absent from shared reading. This demonstrates live post approval and feedback review, alongside the isolated tests of feedback approval, reports and withdrawal. These are demonstration fixtures, not real student experiences, user research or clinical evidence. No email, SMS or Llama generation was requested by the live community workflow. Local screenshots were saved outside the repository as community-moderation-2026-11-08.png and community-feed-2026-11-08.png.

## Remaining work

This adds community moderation, not full administration of users or resource approval. Human moderation policy, staffing, reporting/response expectations, data-retention review, student usability evaluation and supervised safety evaluation remain. Public HTTPS deployment, real-device PWA installation and broader hosting tests remain outstanding. SMS remains on hold. No academic completion percentage or clinical validity is claimed.
