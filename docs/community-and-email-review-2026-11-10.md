# Community connections and email delivery review — 10 November 2026

## Findings

Community submissions and responses were being stored for moderation. The student interface had no automatic updates, no reply counts or notification inbox, and no link from a submitted response back to its reflection. A moderator's own pending submissions are deliberately excluded from their review queue; this requires another moderator rather than self-approval.

The running installation uses `CONTACT_DELIVERY_MODE=local_demo`, with contact invitations and check-in sending switches enabled. This mode permits the approved presentation account and configured verified mailbox only. Its single authorised check-in demonstration allowance has been used. It is not unrestricted production sending.

A read-only lookup of Brevo's events for the two recorded provider references confirmed:

- Invitation: delivered on 8 November at 14:24:35 and opened at 14:25:47 (UTC+3).
- Check-in demonstration: delivered on 8 November at 14:36:02 and opened at 14:36:59 (UTC+3).
- The subsequent check-in attempt on 9 November was blocked by the presentation allowance. It did not send a new message.

No email addresses, tokens, provider references, keys or message bodies are included in this checkpoint. No new real email or SMS was sent during this review. Provider acceptance in an application record does not by itself confirm delivery; the historical delivery evidence above came from Brevo's event lookup.

## Changes

- Visible community views check for updates every ten seconds and when the browser regains focus. Unchanged cards, moderation checklists and writing drafts are preserved; polling stops on logout and skips hidden pages and active requests.
- Feed and My sharing show counts of published replies. Submitted responses identify and link to their parent reflection, with a clear waiting-for-review cue.
- Authors see flower-labelled new-petal notices only after a reply is published. Notices open the correct reply page, including later pages.
- Read receipts persist in the new `community_reply_reads` table. Only the reflection's owner may acknowledge its currently published replies. Opening one page does not clear unread replies on other pages. Rejected/withdrawn replies and withdrawn parent reflections are excluded from activity.
- Moderators see an explanation and count for their own submissions requiring another reviewer. Approval, ownership, flag and stale-revision checks remain enforced.
- The trusted-contact screen now shows invitation recipient, request date, delivery outcome, actual sending eligibility and latest check-in attempt. It displays the presentation restriction even when its one-mailbox connector is configured.
- Reopened chat receipts explain that reopening does not send a fresh email. New alert receipts include their original request timestamp.
- No existing community publication decision, role, contact permission, private entry or sending configuration was changed.

## Verification

| Check | Result |
| --- | --- |
| Community backend, including multi-page reply notices and access boundaries | 77 checks passed |
| Community interface, automatic updates, draft/checklist preservation, reconnection and notification navigation | 29 checks passed |
| Local email demonstration policy | 22 checks passed |
| Live invitation policy | 38 checks passed |
| Production alert policy and functional integration | 37 checks passed |
| Invitation interface, dated receipts and presentation allowance | 10 scenarios passed |
| Human-support interface | 14 checks passed |

Database tests use PostgreSQL temporary tables and fake providers, with original public-table counts checked before and after. No real transport is invoked by these suites. The schema addition creates the read-receipt table without rewriting existing records. Browser inspection verified the updated contact status, published reply count, pending-response cue and moderator queue on the local application.

## Demonstration and remaining setup

Submit a reflection using one student account. Use a different moderator account, review its content, tick the checklist and approve. The published reflection appears in Read together. Repeat for a supportive response; its author can follow it under My sharing, and the reflection's owner receives a new-petal notice after approval. No existing real submission was approved as part of this verification.

The existing Demo Student account already has moderator access. It can review other students' submissions. Its own pending sharing needs another reviewer; this checkpoint grants no additional account privileges.

Invitations and check-in emails are addressed to the nominated trusted contact, not automatically copied to the student's login email. General sending still needs a reachable public HTTPS deployment, verified Brevo setup and reviewed production activation. Signup automatic-invitation opt-in remains off on this laptop. Live SMS remains on hold.

Install ENWEN is a Progressive Web App installation: a desktop window on supported PCs or an app/home-screen entry on supported phones. Phone use requires a reachable HTTPS deployment; a phone's localhost address does not reach the development laptop. Phone installation has not yet been verified on a real device.
