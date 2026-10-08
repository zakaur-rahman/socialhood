# Landing page screenshots

The product screenshots on the landing page (`public/marketing/*.webp`) are taken from the real
app, on the isolated end-to-end stack, with sandbox data. Refresh them whenever the screens they
show change.

| File | Where it is used | What it shows |
|------|------------------|---------------|
| `inbox.webp` | Hero, the product reveal | The inbox (1440 × 900) with an AI draft waiting |
| `connect.webp` | How it works, step 1 | A connected Instagram account and its AI mode |
| `knowledge.webp` | How it works, step 2 | An FAQ in the knowledge base |
| `ai-draft.webp` | How it works, step 3 | A conversation and its AI draft |
| `automation-preview.webp` | The automation showcase | The automation editor's preview: comment, tap first, link, follow nudge |

All are 2× (device scale factor 2), dark, WebP at quality 85, encoded by Chromium.

## Run it

1. Start the e2e stack and keep it up, with your own ports, database and Valkey db (never 3000,
   8000, the `socialhood` database or Valkey db 0; see `docs/testing-e2e.md`). From the
   repository root, in bash:

   ```sh
   E2E_API_PORT=8137 E2E_WEB_PORT=3137 E2E_DB_NAME=socialhood_e2e_shots \
   E2E_REDIS_URL=redis://127.0.0.1:6379/14 node scripts/e2e-stack.mjs --serve
   ```

2. In another terminal, in `apps/web`:

   ```sh
   pnpm shots:marketing
   ```

   It signs the e2e user in (the suite's `auth.setup.ts`), seeds a new workspace, captures the
   five screens and overwrites `public/marketing/*.webp`, printing each file's size.

3. Stop the stack (Ctrl-C). Check the images, then update the sizes in
   `src/components/marketing/shots.ts` if a screen changed shape:
   `src/components/marketing/shots.test.ts` fails until they match the files.

## The demo data

Everything is seeded through the stack's own helpers and the API: a sandbox Instagram account
(which backfills three posts, three conversations and a few comments), four DMs, two "LINK"
comments, four knowledge sources and an active comment-to-DM automation with tap first and the
follow nudge. The fake AI drafts the same reply to every question, so the hero's question is one
that reply fits; the demo DMs' intents are set through the owner's correction endpoint.

The names are made up. The sandbox calls its customers "Sandbox customer 1a2b", its account
"Sandbox shop" and shows a Sandbox badge, and the e2e user has a test email. The capture wraps the
page's `fetch` so those read as "Indigo Lane", first names with an initial and no email
(`installRewrites` in `capture.spec.ts`). Nothing else on screen is changed.
