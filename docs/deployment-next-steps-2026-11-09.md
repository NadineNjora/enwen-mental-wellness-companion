# Taking ENWEN from this laptop to a public website

Status: deployment preparation, not a deployed website. No hosting account, server, domain purchase or public address has been supplied. The laptop, database and local Ollama remain the working installation. No private records or secrets have been uploaded.

## Choose where it will run

For this implementation, one Linux server can run FastAPI, PostgreSQL, Ollama/Llama 3.2 and the HTTPS proxy together. An existing university server and subdomain would avoid a new hosting purchase. A cloud VPS is another option; the owner needs to choose its cost limit and create the account. [Hetzner Cloud](https://www.hetzner.com/cloud/) is one provider to investigate, not a purchase made for this project.

For a small demonstration, plan around 4 vCPUs, 8 GB RAM and at least 60 GB SSD as an initial engineering estimate, then measure generation time and memory on the selected machine. This is not a tested capacity guarantee. CPU-hosted Llama can still be slow; more users or faster replies may need a GPU or a separately approved model host. No paid AI fallback has been enabled.

Keep the public app and the current local database separate at first. Demonstrate with fictional accounts on the server. Moving existing student records is a separate, explicit migration; never upload the local `.env` or database to GitHub.

## Server setup sequence

1. Create or obtain a Linux server and a hostname you control. Ubuntu 24.04 LTS is a straightforward option. Point its DNS record to the server's address.
2. Install Docker Engine and the Compose plugin using [Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). Permit public HTTP/HTTPS to the proxy and restrict SSH to the operator. Do not publish PostgreSQL, Ollama or the internal app ports.
3. Clone the project onto the server. Inside `deploy`, create the ignored `.env.production` from `.env.example`. Enter the real hostname and **new** random database and JWT secrets privately. Do not reuse the laptop's database password.
4. From the project root, validate with `python deploy/check_config.py --env deploy/.env.production`. This checks values only; it does not prove DNS, sender readiness or deployment success.
5. Build and start the private database and Ollama services using `docker compose --env-file deploy/.env.production -f deploy/compose.yaml up -d db ollama`.
6. Download the pinned model with the same Compose prefix followed by `exec ollama ollama pull llama3.2:3b`. Model storage remains in the private Ollama volume.
7. Build and start the app and proxy with the same prefix followed by `up -d --build web proxy`. Caddy needs the real hostname, reachable ports and correct DNS to obtain HTTPS certificates. See [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).
8. Verify the public home page, `/health/db`, registration/login, refresh/logout, private records, Nia's ordinary reply, and a fictional safety interruption **without contacting anyone**. Then test a phone over mobile data, including installation and login after refresh. Local `127.0.0.1` is not the public address.

The application image built successfully on the laptop during this review. The full Compose stack still needs a run on the chosen server. Do not interpret a build or configuration check as completed deployment. Existing `deploy/DRAFT.md` records the packaging limits.

## Enable email deliberately

Brevo is the real email provider. Mailpit is a local developer capture inbox; it is no longer a second student invitation form. Brevo accepting a request does not establish inbox delivery or a human response.

The current laptop remains in restricted local-demo mode. The user approved developing a separate, unticked signup email choice. Its `SIGNUP_CONTACT_INVITATIONS_ENABLED` default is false and it cannot run in local-demo mode. Existing accounts are not automatically enrolled. A failed or unconfigured signup invitation does not erase the new account, and is never automatically retried.

On the public server, use `CONTACT_DELIVERY_MODE=production`, a matching HTTPS `PUBLIC_APP_URL`, a verified Brevo sender and an enabled contact invitation connection. Recipient acceptance and the student's separate check-in permission are still required for contact alerts. Use [Brevo's transactional-email setup](https://developers.brevo.com/docs/send-a-transactional-email). Keep keys only in the server's private environment.

Before activation, revise the production privacy/consent wording with the supervisor, define the intended test audience, and conduct a new explicitly authorised end-to-end invitation/acceptance/check-in test to an agreed mailbox. Historical test consents do not silently become permission for real notifications. The existing Compose file deliberately overrides live-email switches to false; activation must be an explicit reviewed deployment configuration change. SMS remains on hold.

## Release evidence to capture

- The public HTTPS address loading from outside the laptop's network.
- Independent student accounts cannot read each other's journals, moods, chats or bookmarks.
- Registration invitation choice is unticked, optional and accurately reports its result.
- The recipient can accept, decline and withdraw; contact alerts require both parties' choices.
- A fictional danger phrase pauses Nia immediately, including when ordinary inference is unavailable.
- Delivery failures are visible and never reported as a delivered message or promised response.
- One phone installation and a backup restored to a separate test database.
- Measured AI latency and user feedback, with limitations recorded.

Optional emails to students after several low-mood days are a separate feature from trusted-contact safety emails. They are not implemented in this checkpoint. They need their own opt-in, verified student mailbox, a clear trend rule, unsubscribe controls and duplicate protection. Nia must not be described as clinically analysing every journal or predicting danger from mood scores.

AI assistance for curators could later suggest a summary from source text the curator provides. It must remain a reviewed draft, not automatic scraping/publication or permission to copy publisher images or articles. That enhancement and media embedding were not added to this review.
