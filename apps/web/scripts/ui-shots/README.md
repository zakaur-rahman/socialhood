# UI screenshots and axe (visual QA)

Screenshots of every screen in `docs/ui-audit/AGENT_CONTEXT.md` §11 at **375, 768, 1280 and 1536
px**, plus axe at 375 and 1280, from the real app on the isolated e2e stack with sandbox data.
UI-019 took the baseline with it (`docs/ui-audit/qa/baseline.md`); every UI task uses it for its
before-and-after shots (IMPLEMENTATION_PLAN §H, item 8).

- Dark, device scale factor 1, Chromium. Touch emulation (`hasTouch`, `isMobile`) below 1024 px,
  so at 375 and 768. Heights: 812, 1024, 800 and 864 px.
- **Touch widths keep a coarse pointer** (the primitives' `pointer-coarse:` touch sizes depend
  on it):
  - Chromium's beyond-viewport capture, which Playwright's `fullPage` uses, drops touch
    emulation: it renders the page with `pointer: fine` (desktop control heights, the page's
    touch height, so blank space at the bottom) and leaves the page fine afterwards. So at 375
    and 768 a full-page shot is **stitched from viewport captures**. The page never scrolls: each
    tile after the first moves `<body>` with a transform, so sticky bars, scroll-linked effects
    (the landing page's) and viewport units stay in their scroll-0 state, as `fullPage` draws
    them, and fixed elements show in the first screen only; the page is restored before axe runs.
    At 1280 and 1536 the tool keeps `fullPage` (its text anti-aliasing differs slightly from a
    viewport capture on desktop).
  - Touch emulation is also forced from a second CDP session (`Emulation.setTouchEmulationEnabled`;
    `Emulation.setEmulatedMedia` ignores `pointer` and `hover` in Chromium).
  - Before and after each shot the tool checks `matchMedia`: `(pointer: coarse)`,
    `(any-pointer: coarse)` and `(hover: none)` match at 375 and 768 and not at 1280 or 1536, or
    the shot fails. `meta/*.json` records the pointer.
  - Shots taken before this fix (the UI-019 baseline and task folders until 2026-10-07) show
    desktop heights in full-page touch shots, and their axe at 375 ran on that fine-pointer page.
- Full page where the page scrolls; the viewport for "viewport-only" screens (an open dialog,
  menu, drawer or toast, and the banner over the inbox).
- A full-page shot wider than its width means the page scrolls sideways (Home at 375 is 499 px
  wide today, UI-ISS-018). In a full-page shot, sticky and fixed bars (the composer's action bar,
  the settings save bar) appear where they sit in the first screen, over the content below them.
- One test per screen and width, titled like its file: `<screen>-<width>`, so `--grep` picks them.
- axe tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` (`@axe-core/playwright`).

## Run it

1. Start the e2e stack and keep it up, with **your own** ports, database and Valkey db (never
   3000, 8000, the `socialhood` database or Valkey db 0; see `docs/testing-e2e.md`). From the
   repository root, in bash:

   ```sh
   E2E_API_PORT=8136 E2E_WEB_PORT=3136 E2E_DB_NAME=socialhood_e2e_qa \
   E2E_REDIS_URL=redis://127.0.0.1:6379/6 node scripts/e2e-stack.mjs --serve
   ```

   It builds the web app from your working tree (`--skip-build` reuses the last build), so the
   shots show your branch's code.

2. In another terminal, in `apps/web`, with an output folder **outside the repository**
   (screenshots are never committed):

   ```sh
   UI_SHOTS_OUT=/c/Users/me/social-auto/design/ui-qa/my-task-before pnpm shots:ui
   ```

   Sign-in needs the Clerk development keys, like the e2e suite: from the environment
   (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`) or `apps/web/.env.local` and
   `apps/api/.env`.

3. Stop the stack (Ctrl-C). It drops its database.

A full run is 125 shots in about 15 minutes on one worker (the baseline: 15 min 9 s): seeding takes
25 s to 2 minutes, then 4 to 10 seconds a shot. Tests retry twice: on a laptop a network change
(`ERR_NETWORK_CHANGED`) or a slow Clerk script occasionally stalls a page. A run into a new folder
seeds new workspaces; one into the same folder on the same stack reuses them.

### Options

| Variable | |
|---|---|
| `UI_SHOTS_OUT` | Required. An absolute folder outside the repository. |
| `UI_SHOTS_WIDTHS` | A comma list, e.g. `375,1280`. Default `375,768,1280,1536`; axe runs only at 375 and 1280. |
| `UI_SHOTS_REDUCED_MOTION=1` | Renders with `prefers-reduced-motion: reduce` (use a separate folder). |

Playwright arguments go after the script: `pnpm shots:ui --grep "conversation-"` (one screen,
every width), `--grep "375$"` (every screen at one width), `--grep "settings-"`, `--list`.

## What it writes

| File | |
|---|---|
| `<screen>-<width>.png` | The screenshot. |
| `axe/<screen>-<width>.json` | axe at 375 and 1280: each violated rule's id, impact, node count, targets and the elements' opening tags; and the "needs review" rules with node counts. |
| `axe.json` | All of them, with totals per rule. |
| `axe-summary.md` | The totals by rule (violations, then needs review), and a table per screen and width. |

axe skips placeholder text and can't decide contrast over background images, gradients and
overlapping elements: everything in the sidebar (its background image) lands in "needs review",
including the group labels that fail at 3.64:1 (UI-ISS-007). A contrast fix may show there rather
than in `color-contrast`; the summary gives axe's reason for each.
| `meta/*.json`, `shots.json` | Each shot's URL, size, whether it is full page, and loading warnings. |
| `.seed.json` | The seeded workspaces for this stack (reused by later runs on the same stack). |

The summary files are rebuilt from `axe/` and `meta/` after every run, so a `--grep` run into the
same folder updates its own screens and keeps the rest (each entry has its time).

## The screens

`screens.ts` lists them in order, with what each shows and what it waits for:

home, inbox-list, conversation (an AI draft waiting), comments, post-comments, automations,
automation-editor, template-gallery, schedule-week, schedule-month (below 768 px both show the
agenda), schedule-list, composer, knowledge, ask-panel, ask-page, settings-connections,
settings-ai, settings-workspace, settings-notifications, settings-billing, settings-agent,
upgrade-dialog, menu-open (an automation's ⋯ menu), dialog-open (Disconnect), phone-drawer (375
only), toast, banner (Home with an account needing reconnection), banner-inbox (a conversation
under that banner), landing, privacy, data-deletion, sign-in. The last four are signed out.

To add a screen, add an entry to `SCREENS`: a name, what it shows and an `open` that navigates and
waits for real content (a heading, a row, a value), never a fixed time.

## The data

`seed.ts` seeds through the stack's helpers and the API, once per stack (cached in `.seed.json`):

- **QA Shop**: a sandbox Instagram account (it backfills three posts, three conversations and some
  comments), four knowledge sources, an active comment-to-DM automation and a draft one, five
  customer DMs (the e2e worker's fake AI drafts a reply to each; one carries `[e2e:unknown]`, so
  the AI can't answer it and Knowledge shows a gap), four comments, three scheduled posts and a
  draft post for the composer.
- **QA Reconnect**: a second workspace whose account needs reconnecting (a reply the sandbox
  refuses with `account_needs_reconnect`), for the banner shots.

Nothing is rewritten: the sandbox's names ("Sandbox customer mj01", "Sandbox shop", the Sandbox
badge) and the test user ("Esme Tester") are what the app shows. Remote pictures (sandbox posts,
seeded uploads) are answered with a grey placeholder with a cross, so no shot reaches the network
for images and thumbnails keep their shape.

Not frozen: relative times ("now", "2d"), the greeting (by time of day), the calendar's dates, the
AI credits used. Two runs differ there, and in the sandbox's random account handle when the stack
was restarted between them.

## Before and after

1. **Before**: on your branch's starting point (or `develop`), start the stack and run the tool
   into a "before" folder. Stop the stack.
2. Make the change. Start the stack again (it rebuilds) and run the tool into an "after" folder,
   with the same widths and screens (`--grep` for the screens your task touches).
3. Compare, from `apps/web`:

   ```sh
   node scripts/ui-shots/compare.mjs <before-folder> <after-folder> [<out-folder>]
   ```

   It compares every PNG present in both, pixel by pixel in headless Chromium (a channel moving
   by more than 24 counts), writes a diff image per changed shot (the after dimmed, changes in
   magenta) and `index.html` with before, after and diff side by side, most-changed first, and
   lists the added and removed files. The default output is `<after-folder>/diff`.

4. For axe, compare the two `axe-summary.md` files (or `axe.json`'s `rules`): no new rule on a
   touched screen, and the task's targeted rules gone (§H, item 3).

Expect small diffs from the dynamic text above; look at the diff image before filing anything.
Attach the before, after and diff images of the touched screens to the PR (§H, item 8).
