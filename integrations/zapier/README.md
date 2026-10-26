# Social Hood for Zapier

The source of Social Hood's Zapier integration (GR-26), a [Zapier Platform CLI](https://docs.zapier.com/platform/build-cli/overview)
app. It is not part of the pnpm workspace and has no lock file here: nothing in this folder is installed or run by the
monorepo's CI. It was written against `zapier-platform-core` 16 and has not been run yet (the sandbox that wrote it had no
Zapier account); the first `npm install && npm test` is step one below.

The integration calls the Social Hood **public API** (`/public/v1`, GR-25) with a workspace API key. The public API,
API keys and Zapier are part of the **Pro and Max** plans (PD-6). Outbound webhooks stay on every plan.

## What it does

| Kind | Name | Calls |
| --- | --- | --- |
| Trigger (REST hook) | New Contact | `contact.created` |
| Trigger (REST hook) | Lead Captured | `lead.captured` |
| Trigger (REST hook) | Tag Added to Contact | `contact.tagged` (additions only; optional tag) |
| Trigger (REST hook) | New Message from Customer | `message.received` |
| Trigger (REST hook) | Automation Run Completed | `automation.run.completed` |
| Action | Add Tag to Contact / Remove Tag from Contact | `POST /contacts/{id}/tags` |
| Action | Set Contact Field | `PATCH /contacts/{id}` with `fields` |
| Action | Send Message | `POST /conversations/{id}/messages` (inside the 24-hour reply window) |
| Hidden | Tag, Contact Field | fill the dropdowns |

How a trigger works: turning a Zap on calls `POST /public/v1/hooks {trigger, target_url}`, which makes a webhook endpoint
on the workspace (GR-04). Social Hood then delivers each event to Zapier signed, retried and logged exactly like any
webhook endpoint; the deliveries show in Settings, Integrations. Turning the Zap off calls `DELETE /public/v1/hooks/{id}`.
Revoking the API key removes its hooks. Each trigger also has a polling list (`performList`), which Zapier uses to test
the trigger and fetch sample data: contacts by `sort=created`, conversations, automation runs.

## API key scopes

Make a key in Social Hood: **Settings, Integrations, API keys, Create API key**. For every step in this app:
`contacts:read`, `contacts:write`, `tags:read`, `tags:write`, `conversations:read`, `messages:send`,
`automations:read` and `webhooks:subscribe`. A key can have fewer; a step whose scope is missing fails with the API's
"This API key doesn't have the … scope." The key is shown once.

## First run

```sh
cd integrations/zapier
npm install
npm test          # jest, with nock standing in for the API; no network
npx zapier validate
```

`API_BASE_URL` defaults to `https://api.amplychat.com`. For a staging API, set it on the version with
`npx zapier env:set 1.0.0 API_BASE_URL=https://api.staging.example`.

## Push a private version

```sh
npx zapier login
npx zapier register "Social Hood"        # once; writes .zapierapprc (commit it)
npx zapier push                           # uploads the current version, private to your account
npx zapier users:add you@example.com 1.0.0   # invite people to use the private version
```

Before the first push, add `icon.png` here: **256 x 256, PNG**. Resize `apps/web/public/icons/icon-512.png`
(for example `magick icon-512.png -resize 256x256 icon.png`). `zapier validate` lists anything else missing.

## The manual test: captured leads to a Google Sheet

The coordinator cannot run Zapier, so this is the check that GR-26 is done. Needs a Pro or Max workspace with an
automation that asks for an email (a flow with an "ask for email" step) and a Google account.

1. In Social Hood make an API key with the scopes above.
2. In Zapier (the private integration from `zapier push`) make a Zap: trigger **Social Hood, Lead Captured**; connect
   with the key (the connection is named after the workspace). Test the trigger: it shows a recent contact with an
   email (the polling sample).
3. Action **Google Sheets, Create Spreadsheet Row** on a sheet with the columns `Name`, `Username`, `Platform`, `Email`,
   `Captured`. Map `contact name`, `contact username`, `contact platform`, `captured value` and `occurred at`.
   Turn the Zap on.
4. In Social Hood, Settings, Integrations: a new endpoint "Zapier: lead captured" appears, on.
5. Send the Instagram or WhatsApp account a message that starts the automation, and answer its email question.
6. Within a minute a row appears in the sheet, and the endpoint's delivery log shows `lead.captured` delivered (200).
7. Turn the Zap off: the "Zapier: lead captured" endpoint disappears.

Also try: **New Contact** with a Slack message, **Add Tag to Contact** after **New Message from Customer**, and **Send
Message** with the trigger's Conversation ID (a closed window shows "The 24-hour reply window has closed.").

## Getting it into Zapier's app directory (the owner's track)

Nothing here needs the repo; it is Zapier's review. In rough order (check Zapier's current checklist when you start,
it changes):

1. Run the manual test above on the private version, with a second person's Zap too.
2. Make a **review account**: a Pro workspace with sample contacts, a flow that captures an email, one API key with
   all scopes. Zapier's reviewers ask for sign-in details and it must not expire.
3. Fill in the app's details in the Zapier developer dashboard: description, icon (256 px PNG), category, support
   email, the links to the public API reference (`/developers/api`), the Privacy Policy and the Terms.
4. `npx zapier promote 1.0.0` and wait for the review. Fix what they ask for and push a new version
   (bump `version` in `package.json`; keep the API's behaviour backwards compatible, since Zaps pin a version).
5. After it is live, announce it, and watch for failing Zaps in the dashboard.

## Make

Make (Integromat) follows with the same building blocks: the same API key, scopes, REST hooks and polling lists.
It needs its own app definition and is not started here.
