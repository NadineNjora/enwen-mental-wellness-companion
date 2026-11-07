# Student experience refinement

Completed 5 November 2026.

## Changes

- The green header badge shows the signed-in display name and clears on logout.
- History fetches all pages of the authenticated student's saved moods. The entry
  list is paginated in groups of 20. Original 1–5 and current 1–10 scores are drawn
  in separate panels using a shared date range; no recorded scores were converted.
- Removed the stray question mark from the journal label and repetitive development
  labels from page introductions, forms and navigation. Existing versioned consent
  texts were retained rather than silently changing previously recorded terms.
  Delivery status still explains that invitations stay local and live alerts are off.
- The catalog expanded from 5 to 13 entries. Added Strathmore, Daystar, Kindred
  Collective, Befrienders Kenya, USIU-Africa, Mount Kenya University, NHS grounding
  and NHS breathing. Existing resource IDs and bookmarks were retained.
- Breathing now uses four rounds of inhale/hold/exhale/rest, four seconds per phase,
  totalling 64 seconds. A code-based SVG flower changes size with the phase and
  freezes when paused. Affirmations are separate from a five-senses grounding area.
  The still-flower control honours the device's initial reduced-motion preference.
- Grounding includes physical support, softening jaw/shoulders, five things seen,
  four felt, three heard, two smelled and one tasted, plus a next-step reflection.
- Older accounts with no trusted contact now see an add-person form. POST
  /trusted-contact requires current wellness consent and explicit, versioned contact
  permission. A user-row lock and existing unique constraint prevent duplicates.
  Saving creates a pending person plus one consent record atomically, with no email.

## Checks

- 84 real-PostgreSQL TEMP-table contact/registration checks passed, including older
  accounts, absent/stale permission, self-addresses, cross-user attempts, duplicate
  setup and no automatic invitation. Tests rolled back with public counts unchanged.
- 25 resource API checks passed against the expanded catalog in isolated TEMP tables.
- Frontend scenarios passed: 25 journal/history, 19 resources/breathing, 7 contact
  setup, 11 contact dashboard, 12 registration, 12 prompt helpers, 7 invitation response.
- The history test includes 101 records over two API pages, both scales plotted,
  20 visible list records, and Older/Newer navigation.
- Browser verified Demo Student in the badge; history from 21 September to
  4 November with 13 original-scale and 2 current-scale entries; all 13 resources;
  corrected journal label; the older-account contact form; changing flower scale,
  phase text, affirmations, and working pause controls. No contact was added to the
  user's real demo account and no invitation was sent during browser review.
- JavaScript syntax, git diff --check, asset serving and database health passed.
- Visual review used the desktop viewport. Responsive breakpoints are included;
  a separate phone viewport was not exercised.

## Source checking

Strathmore and university service descriptions came from their original-domain
pages/search results. The Kindred site supplied by the user was opened in the
browser and its service descriptions inspected. This verifies the source identity,
not independent clinical accreditation. Befrienders Kenya's support-page link was
checked using the helpline connector; no unverified telephone details were added.

Breathing rhythm reference:
https://www.southtees.nhs.uk/resources/brief-techniques-to-manage-anxiety/

Grounding reference:
https://www.nhsinform.scot/healthy-living/mental-wellbeing/breathing-and-relaxation-exercises/grounding-exercises

Saved screenshots remain outside the public repository in ENWEN-tutorials.
Changes are local and uncommitted; no Git push or deployment was performed.
