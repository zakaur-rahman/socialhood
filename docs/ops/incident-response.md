# Incident response: personal data breaches

What to do when personal data may have been exposed, changed, lost or reached by someone who
shouldn't have it. For ordinary alerts see the [runbook](runbook.md). Not reviewed by a lawyer.

The promises this plan keeps (change both together):

- Privacy Policy, "Security and breaches" (`apps/web/src/app/(marketing)/privacy/page.tsx`): tell
  affected people without delay what happened, what it may mean, what we're doing and what they can
  do; report to the Data Protection Board of India and other authorities as the law requires; tell
  the business within 72 hours when its customers are affected.
- DPA, "Breaches" (`apps/web/src/app/(marketing)/dpa/page.tsx`): tell the workspace owner without
  undue delay and within 72 hours of becoming aware, with what happened, the data and people likely
  affected, the likely consequences and what we're doing, then more details as we learn them.

## 1. Who decides

The owner decides everything here: whether it is a breach, what to switch off, who to tell and
what to say. Anyone else who notices something (an alert, a Sentry event, an email to support@)
tells the owner at once and doesn't wait to be sure.

The clock starts when we **become aware**: when we have reasonable grounds to think personal data
was affected. Write that time down first (step 3).

## 2. Contain, then rotate

Stop the leak before anything else. Keep evidence: don't delete logs, containers or the database.

- **Take the API offline if data is still leaking:** on the VM, `docker compose stop api worker`
  in `/opt/amplychat` (the website stays up; [deploy-vm.md](deploy-vm.md)). Roll back a bad deploy
  with `./deploy.sh --rollback`.
- **Save evidence:** `docker compose logs --no-color > /root/incident-<date>.log` for `caddy`,
  `api`, `worker` and `web`. Container logs keep only 5 files of 10 MB each, so copy them early.
  Export the relevant Sentry events.

Then rotate whatever may have leaked. Every secret lives in `/opt/amplychat/api.env`,
`postgres.env` or `web.env` on the VM (`amplychat-prod`), or in GitHub Actions secrets. Restart
`api` and `worker` (and `web` for Clerk) after changing them.

| System | Secrets | How |
| --- | --- | --- |
| VM access | `VM_SSH_KEY` (GitHub Actions), GCP accounts | Remove the key from the VM and GitHub; check GCP IAM and the project's audit log |
| Postgres (on the VM) | `POSTGRES_PASSWORD`, `DATABASE_URL`, `DATABASE_URL_DIRECT` | `ALTER ROLE ... PASSWORD`, then update `postgres.env` and both URLs in `api.env` together |
| Valkey (on the VM) | none: no password, only on the internal `data` network | Check it wasn't published; it holds no durable data |
| Backups | `BACKUP_GCS_BUCKET` (off-site copies) | Check who can read the bucket; dumps on the VM under the backup directory ([backup.md](backup.md)) |
| Stored tokens | `TOKEN_ENCRYPTION_KEYS` | Put a new key first, keep the old ones after it. Old tokens stay readable with the old key, so if the key and the database both leaked, treat every stored Meta, Google and Shopify token as leaked (next rows) |
| Clerk | `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET` | Roll in the Clerk dashboard; end sessions there if accounts may be taken over |
| Meta | `META_APP_SECRET`, `IG_APP_SECRET`, `IG_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Reset in the Meta App Dashboard. Resetting the secret doesn't revoke tokens already given to businesses: if those leaked, ask the owners to disconnect and reconnect, and ask Meta for help |
| Gemini | `GEMINI_API_KEY` | Delete and create a key in Google AI Studio / Cloud console |
| Google (Sheets, YouTube) | `GOOGLE_CLIENT_SECRET`, `YOUTUBE_CLIENT_SECRET` | Reset in the Google Cloud console |
| Shopify | `SHOPIFY_API_SECRET` | Rotate in the Shopify Partner dashboard |
| Cloudinary | `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Create a new key, then disable the old one |
| Dodo Payments | `DODO_API_KEY`, `DODO_WEBHOOK_SECRET` | Roll in the Dodo dashboard. Card data never reaches us |
| Resend | `RESEND_API_KEY` | Delete and create a key in Resend |
| Web push | `VAPID_PRIVATE_KEY` | A new key pair means every device must subscribe again; only rotate if it leaked |
| Monitoring | `METRICS_TOKEN`, `SENTRY_DSN`, `SENTRY_AUTH_TOKEN` | Regenerate; a DSN only lets someone send events |
| Workspace API keys and MCP connections | in the database, hashed | Ask affected owners to revoke and recreate them in Settings |

## 3. Keep a fact log

Start a private file (never in this public repo) and add to it as you go, with times in UTC:

- when and how we became aware, and who noticed;
- what happened, what systems and what data (kinds of data, which workspaces, roughly how many
  people), and whether it is still happening;
- every action taken, by whom and when;
- every notice sent: to whom, when, and a copy of what it said;
- what we still don't know.

Every notice below is written from this log. Keep the log, even for incidents that turn out not
to be breaches, for at least a year.

## 4. Tell people

Send what you know by each deadline; say what you don't know yet and send more later. All
deadlines run from becoming aware (step 1).

| Who | When | How |
| --- | --- | --- |
| CERT-In (India) | **Within 6 hours** of noticing a reportable cyber security incident (data breaches and leaks are on its list) | Email `incident@cert-in.org.in` with the form from cert-in.org.in (CERT-In Directions, 28 April 2022) |
| Workspace owners whose customers' data is affected (we are their processor) | Without undue delay, **within 72 hours** (the DPA) | Email the owner from support@ with what happened, the data and people likely affected, the likely consequences and what we're doing |
| Data Protection Board of India | Without delay a short report, then the **details within 72 hours** (DPDP Rules 2025, Rule 7) | The Board's online form. Details: what happened, the likely impact, what we've done and will do, and that we've told the people affected |
| People whose own data is affected (our account holders: we are the controller) | Without delay (Privacy Policy; DPDP Rule 7) | Email: what happened, what it may mean for them, what we're doing, what they can do, and support@ for questions |
| An EU or UK data protection authority, if people in the EU or UK are affected and it's our account data | **Within 72 hours** unless the breach is unlikely to put people at risk (GDPR Article 33) | The authority of the country where the affected people are. Write down why if we decide not to report |
| Meta | Without undue delay if Instagram, Facebook or WhatsApp data is involved (Meta Platform Terms) | Report through the Meta App Dashboard / developer support for the app |
| Google | If YouTube or Google Sheets data is involved, as Google's API Services User Data Policy requires | Through the Google Cloud console support for the project; check the current policy |
| Subprocessors | If the breach came from or touches one (Clerk, Cloudinary, Dodo, Resend, Sentry, Google) | Their security contact, to contain it on their side |

For customers of a business (people who messaged an Instagram account, a Facebook Page, a WhatsApp
number or a website chat), the business is the controller and tells them. We help it: give it the
facts from the log and draft wording if it asks.

## 5. Afterwards

- Fix the cause, and add a test or an alert so it can't come back silently.
- Check the deleted data really is gone, including backups (they expire within 30 days).
- Write a short note of what happened and what changed, and keep it with the fact log.
- Update this plan if any step didn't work.
