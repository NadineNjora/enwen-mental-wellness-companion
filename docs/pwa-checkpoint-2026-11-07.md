# PWA preparation and safe checkpoint — 7 November 2026

## Implemented

- Root-scoped web app manifest with stable app ID, ENWEN name, standalone launch, theme colours and code-drawn 192/512 PNG flower icons. A 180-pixel Apple touch icon is also provided.
- Install ENWEN control with native prompt handling in supporting browsers and manual Chrome/Edge/Safari instructions otherwise. Installed-mode detection prevents redundant promotion. No automatic install confirmation or browser permission is accepted by the code.
- Root /sw.js route with valid JavaScript MIME, no-cache update checking and Service-Worker-Allowed header. /manifest.webmanifest uses application/manifest+json.
- A public offline page is precached alongside public icons only. Online navigation always requests the server; unreachable navigation falls back to public offline guidance. GET APIs, POST bodies, journals, moods, chat history and session responses are never cached or queued. Updates do not force a page reload or discard drafts. Only this app's previous public cache names are cleaned up.
- The offline page says that saves and notifications cannot be made there, identifies the need to reconnect/start the local server, and provides source-linked Kenyan emergency information. It does not pretend to restore private records or failed submissions.

## Verification and limits

- 11 service-worker/manifest/icon tests passed, including private API exclusion, no POST caching, public-only fallback, cache-upgrade scope and actual PNG dimensions.
- FastAPI public route, MIME, service-worker scope and asset checks passed, without database record access.
- Existing 15 chat-history/safety frontend checks continued to pass.
- Browser: existing Demo Student login restored; the install control and manual instructions rendered correctly. Screenshot saved outside the repository at ENWEN-tutorials/10-prototype-walkthrough/pwa-installation-2026-11-07.png.
- The in-app browser does not expose its service-worker runtime to the browser inspection tool. Worker behaviour was tested in isolation and routes were checked; physical Android/iOS installation and real offline/browser lifecycle remain to be validated in Chrome/Edge/Safari. Do not describe the app as already installed on a phone.

Phone use needs a reachable HTTPS deployment; 127.0.0.1 on a phone refers to that phone, not this laptop. Installing the frontend does not move PostgreSQL, FastAPI or Ollama onto the phone. The current AI remains on the laptop. Production hosting, secure deployment configuration, mobile device testing, live trusted-contact SMS enrollment/permission and evaluated safety screening remain unfinished.

## Source and Git review

Reviewed project source, documentation, tests and tooling for copies of the saved private API keys/JWT secret and common API-key patterns; none were found. backend/.env remains ignored. Generated public icon PNGs contain no account or health data. Runtime records remain in PostgreSQL, and evidence screenshots remain outside the repository. A local commit checkpoints the reviewed application; no public deployment or GitHub push is part of this checkpoint.

Official implementation references:

- https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable
- https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/register
