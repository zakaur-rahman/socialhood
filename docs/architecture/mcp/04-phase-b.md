# 04 · MCP server: phase B (writes, media uploads, Ask)

- **Status:** built on `feature/mcp-b` (from `feature/mcp-core`), 2026-11-01. Deviations and small calls: "C-165 (phase B)" in `docs/CONFLICTS.md`.
- **Design:** [01-design.md](01-design.md), decisions [02-decisions.md](02-decisions.md), phase A [03-phase-a.md](03-phase-a.md).
- **Result:** the catalogue was the design's 25 tools (13 read, 12 new). See "A person approves" at the end for what has changed since; it is 27 tools today.

## The new tools

| Tool | Scope | Role | Access (mode that admits it) | Plan | Hints (read-only / destructive / idempotent / open world) |
|---|---|---|---|---|---|
| `create_post` | `posts:write` | admin | draft (`read_drafts`: drafts only; scheduling needs `full`) | drafts on every plan, scheduling Pro and Max | false / false / true / true |
| `update_post` | `posts:write` | admin | draft (same rule) | scheduled posts Pro and Max | false / true / true / true |
| `cancel_post` | `posts:write` | admin | write | Pro, Max | false / true / true / false |
| `start_media_upload` | `media:write` | admin | draft | all | false / false / true / false |
| `finish_media_upload` | `media:write` | admin | draft | all | false / false / true / false |
| `import_media_from_url` | `media:write` | admin | draft | all | false / false / true / true |
| `draft_reply` | `replies:draft` | agent | draft | all | false / false / true / false |
| `add_knowledge` | `knowledge:write` | admin | write | Pro, Max (see the deviation) | false / false / true / false |
| `pause_automation` | `automations:write` | admin | write | Pro, Max | false / true / true / false |
| `ask_amplychat` | `ask` | agent | read | all (the plan's AI credits, D8) | true / false / true / false |
| `get_ask_answer` | `ask` | agent | read | all | true / false / true / false |

`get_media_upload` (phase A) reads the tickets these tools make. Every write takes an `idempotency_key`. `create_post` and `add_knowledge` also dedupe an identical resend for 15 minutes (10 before C-169). `pause_automation` doesn't: a person may have turned the automation back on, so a replay would swallow a real second pause.

### The prompts

`schedule_a_post` and `weekly_inbox_digest` (`mcp/prompts.py`), listed by `prompts/list`; C-169 added a third, `set_up_comment_automation`. The first walks the member through accounts, media, caption and time, previews with `create_post`, and schedules only after a yes.

## Posts: direct, with safety nets (D3)

1. **Confirmation.** `create_post` (to schedule), `update_post` (on a scheduled post, or giving a draft a time) and `cancel_post` (of a scheduled post) change nothing until called again with `confirmed: true`. The first call returns a **preview** (`preview: true`, `post_id` null for a post not yet created): the resolved time in the workspace zone and UTC, the accounts, and the composer's checklist. The preview runs the real flow inside a savepoint and rolls it back, so its errors are the real errors. A preview is never stored for replay, so the same `idempotency_key` can then do the real thing. Saving a draft needs no confirmation.
2. **Five minutes ahead.** `when` earlier than now + 5 minutes (`MIN_SCHEDULE_LEAD`) is a field error on `when`. There is no "publish now". *(Changed: C-181 gave AI apps their own constant, `AI_APP_SCHEDULE_LEAD`, when the app's lead became 1 minute. Owner, 2026-11-11: AI apps schedule at least 1 minute ahead too, and `when: "now"` publishes right away after a preview and a yes. See the last section.)*
3. **The team is told.** A scheduled, changed or cancelled post notifies the owners and admins (in the app, `ai_post_change`) with the AI app, the member and a link to the post, where it is cancelled.
4. **Free saves drafts only.** `create_post` is a draft-tier tool, so Free (mode capped at `read_drafts`) can call it with `when: "draft"`; any other `when` is `entitlement_required` (`ai_connections`). A Pro workspace set to "read and drafts" gets a plain refusal instead.
5. **Caps.** `mcp_posts_daily`: Creator 100, Business 100, Agency 300 (C-172, C-174; Pro 100 and Max 300 under C-169, and 25 and 100 before), and 20 a minute per workspace (`mcp_posts`), both counted when a post is scheduled.

`when` is one string: an ISO time (an offset, or the workspace zone without one), words like "tomorrow 7 pm" (the Ask resolver), `next_free_slot`, or `draft`. The rules are the composer's: `services/scheduled_posts` (checklist, quota `scheduled_posts_monthly`, formats).

## Media (no bytes through the API)

| Client | Path |
|---|---|
| Claude Code, Codex | `start_media_upload` returns a `curl` command with Cloudinary's signed fields. The AI runs it where the file is (ffmpeg's output), reads `public_id` from the JSON, and calls `finish_media_upload`. |
| claude.ai, Desktop, ChatGPT | `start_media_upload` returns `upload_page_url`. The member opens it (`/w/{slug}/upload/{id}`), picks the file, and it goes to storage and into the library. The AI calls `get_media_upload` until `uploaded` (or `finish_media_upload` without a `public_id`). |
| Any, with a public link | `import_media_from_url`. |

- **Ticket.** `mcp_uploads` row, 30 minutes, one file. Its tag `mcp_upload_{id}` is part of the signature, so the stored file carries it. `finish_media_upload` reads the file back and refuses one without the ticket's tag, or outside the workspace's `post` folder.
- **Limits, early.** `start_media_upload` takes `bytes` and `duration_s` and refuses a file over a limit before anything is uploaded; its result lists the limits: images 8 MB, videos 100 MB (`post_video_max_mb`), Reels up to 15 minutes, Stories 3 to 60 seconds, carousel videos up to 90 seconds. The final check is the library's own (`media_assets.register`), which also starts the eager H.264 render. A file over a limit comes back `rejected` with the reason, and is deleted from storage.
- **Link import and SSRF.** The URL must be `https`. `security/ssrf.probe` resolves the host, requires every address to be public (private, loopback, link-local and metadata ranges are refused, IPv6 mapped forms too), follows redirects by hand (at most 3, each checked), and reads only headers. The content type must be JPEG, PNG, WEBP, HEIC, MP4 or MOV and the declared size within the limit. Only then does Cloudinary fetch the final address.
- **Caps.** Per workspace per UTC day: files `mcp_uploads_daily` (Free 20, Creator 50, Business 200, Agency 1,000) and megabytes `mcp_upload_mb_daily` (500, 2,500, 10,000, 50,000). When phase B was built: Free 20, Pro 200, Max 1,000 and 500, 10,000, 50,000. Counted when a file finishes; a new ticket is refused once the day is used up.

## Drafts, knowledge, automations, Ask

- **`draft_reply`** saves the text (or a draft Amplychat writes from the knowledge base, 2 AI credits) as the conversation's pending reply suggestion, answering the customer's latest message. The inbox shows it like any suggestion. It never sends and there is no send tool. A closed reply window is refused.
- **`add_knowledge`** adds a note or FAQ through `services/knowledge/sources.create`; the plan's characters-of-knowledge limit applies (402). It waits as `awaiting_approval` until a person approves it on the Knowledge page.
- **`ask_amplychat`** creates a normal Ask run (`agent_runs.create`, the `ai` rate limit, the plan's credits), commits, enqueues it for the worker, and waits up to 25 seconds. Longer runs return `ask_run_id` for `get_ask_answer`. The same question twice in two minutes by one connection is the same run.

## Plumbing

- `ToolCall` gained `note(...)` (a line for `audit_events`), `after_commit` (work for after the commit) and `client_name`.
- **Audit mirror.** After a write commits, `calls._run` writes each noted line to `audit_events` ("Asha via Claude Code"). It sits next to phase A's `mcp_tool_calls` row, which is still written for every call. A failing mirror is logged, never fails the call.
- Writes now commit with `events.commit_and_publish`, so the app's live updates (`scheduled_post.updated`, suggestions) reach open browsers.
- New entitlements (`billing/plans.py`): `mcp_posts_daily`, `mcp_uploads_daily`, `mcp_upload_mb_daily`. `plan-table.json` is regenerated.
- New routes for the upload page: `GET /v1/w/{wid}/mcp-uploads/{id}` (the ticket and its signed fields) and `POST …/complete` (owners and admins). `openapi.json` and `schema.d.ts` are regenerated.

## Example: edit a video in Claude Code with ffmpeg, upload it, schedule the Reel

Setup once: a Business workspace (keys need Business or Agency; Pro when this was written), an API key with `posts:read`, `posts:write` and `media:write`, and `claude mcp add --transport http amplychat https://api.amplychat.com/mcp --header "Authorization: Bearer $AMPLYCHAT_API_KEY"`.

> **Member:** Trim `raw.mov` to 30 seconds, crop it to 9:16, and schedule it as a Reel on @maple.bakery for Friday 6 pm with @priya as a collaborator and our usual first comment.

1. Claude Code runs ffmpeg locally: `ffmpeg -i raw.mov -t 30 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:v libx264 -c:a aac reel.mp4`.
2. `get_workspace` and `list_accounts` (who am I, which account, its time zone).
3. `start_media_upload {kind: "video", filename: "reel.mp4", bytes: 18400000, duration_s: 30}` returns `upload_id`, a `curl` command and the limits. Nothing is refused: 17.5 MB, 30 seconds.
4. Claude Code runs the command from the result in the shell. Storage answers with JSON containing `public_id`.
5. `finish_media_upload {upload_id, public_id}` returns `media_id` and `status: "uploaded"` (duration 30 s, format mp4). The H.264 render has started.
6. `create_post {accounts: ["@maple.bakery"], media_ids: [media_id], kind: "reel", caption: "...", first_comment: "...", collaborators: ["priya"], when: "2026-11-06 18:00"}`. The result is a preview: "Preview: this reel would be scheduled for Fri 6 Nov 2026, 6:00 pm Asia/Kolkata (12:30 UTC)", the checklist all passing, `preview: true`. Nothing is stored.
7. Claude Code shows the member the preview. The member agrees.
8. The same call with `confirmed: true` returns `status: "scheduled"` with `post_id` and a link. The owner and admins get a notification, and the audit log shows "Asha via Claude Code: post.scheduled".
9. If the member changes their mind: `cancel_post {post_id}` previews, then `cancel_post {post_id, confirmed: true}` returns it to a draft before it publishes.

Without a shell (claude.ai), step 3 gives `upload_page_url` instead: the member opens it, picks `reel.mp4`, and Claude calls `get_media_upload` (or `finish_media_upload` without a `public_id`) to get the `media_id`.

## Tests

`tests/integration/test_mcp_publish.py`, `test_mcp_media.py`, `test_mcp_writes.py`, plus additions to `tests/unit/test_mcp_registry.py` (the 25 tools and the write tools' scope, role, access and hints) and `tests/tenancy/test_isolation.py` (the upload ticket routes). All use the SDK client against the mounted app, as phase A's do.

## C-169: automations and Instagram posts

Added after launch, because Claude could neither create an automation nor find "my last post". The catalogue is now 28 tools (`mcp/tools/automations_create.py`, and `list_instagram_posts` in `mcp/tools/posts.py`). Decisions: "C-169" in `docs/CONFLICTS.md`. Today's count and what changed are under "A person approves" below.

| Tool | Scope | Role | Access | Plan | Hints (read-only / destructive / idempotent / open world) |
|---|---|---|---|---|---|
| `list_instagram_posts` | `posts:read` | agent | read | all | true / false / true / false |
| `create_automation` | `automations:create` | admin | write | Pro, Max | false / false / true / false |
| `update_automation` | `automations:create` | admin | write | Pro, Max | false / true / true / false |

- **`post`.** `resolve_post` (`mcp/tools/common.py`) is the one reader of a post id or `latest`, used by `create_automation`, `update_automation`, `get_post_comments_summary` and `get_analytics_summary` (`post_id`). `latest` is the first item of `list_instagram_posts`, without Stories (they take no comments), of `account` when given. The automation tools also take `next` and `any`.
- **`create_automation`** goes through the editor's services: `definitions.create` and `definitions.update` (the autosave PUT). It is always saved off. Without `confirmed` the same calls run inside a savepoint, so its errors are the real ones. The result shows the account, the post, the keywords, the DM, the public reply, the tap first opening, overlaps with live automations (`queries`, FR-AUT-15), what activation would still refuse (`flow_store.problems`) and active automations used and allowed. Identical confirmed calls dedupe for 15 minutes, as long as a confirmation token lasts (`create_post` too).
- **`update_automation`** sends the stored definition back with only the fields given. It refuses a flow, an AI reply, an image, Live comments and other triggers, with a link to the editor. It doesn't turn anything on or off, and it refuses an automation that is on: pause it first, and a person turns it back on in the dashboard.
- **Told and recorded.** `ai_automation_change` notifies owners and admins; `automation.created` and `automation.updated` go to the audit mirror.
- **Prompt.** `set_up_comment_automation` (`mcp/prompts.py`).
- **Preview, enforced.** `mcp/confirmations.py`: a confirmed change needs the preview's `confirmation_token` (01-design.md §6.6). This also applies to `create_post` (scheduling), `update_post` and `cancel_post`; item 1 of "Posts" above now means this.
- **Scope.** The two automation tools need `automations:create`; `automations:write` is pause, so existing connections don't gain them.
- **Tests.** `tests/integration/test_mcp_automations.py`.

## A person approves

AI apps can draft what customers would be told unattended, and a person approves it in the dashboard. This holds whatever an app's own confirmation setting is, and there is no switch to turn it off. The catalogue is 27 tools.

- **Automations.** AI apps can create, change and pause. `create_automation` always saves the automation off and links to it (`dashboard_url`, `next_step`); `turn_on` and `resume_automation` are gone. `update_automation` refuses one that is on (`conflict`, with a link): pause it first, and a person turns it back on, which is when they see the change. Pausing stays direct.
- **Knowledge.** `add_knowledge` stores the source as `awaiting_approval`. It isn't queued, read in or embedded, and it has no chunks, so every path that reads chunks of `ready` sources leaves it out (`repositories/knowledge.nearest_chunks`, for auto replies, suggestions, Ask, the website chat, MCP search and automation AI replies, and `drafting.knowledge_mentioning`). An edit in the dashboard keeps it waiting. `POST /v1/w/{wid}/knowledge-sources/{id}/approve` (owners and admins) makes it `pending` and queues ingestion, and `knowledge.approved` goes to the audit log. It counts toward the plan's characters while it waits. `add_knowledge` is the only MCP knowledge write, and nothing from MCP edits a source.

## Changed on 2026-11-11: the audit and three owner decisions

The MCP audit of 2026-11-11 and the owner's decisions the same day changed the rules above. The tools themselves are described by their own code and by the generated list on `/developers/mcp`.

- **One minute, not five (owner).** An AI app schedules at least 1 minute ahead, the same as in the app. The pages no longer present a wait as a safety window.
- **Publish now (owner).** `create_post` and `update_post` take `when: "now"` and publish right away, after a preview and a yes. Paid plans, Full mode, owners and admins, as for scheduling.
- **Automations on and off (owner).** An AI app can turn an automation on as well as pause it, each after a preview and a yes. This replaces "a person turns it back on" in "A person approves" above. A new automation is still saved off, `update_automation` still refuses one that is on, and knowledge still waits for a person's approval.
- **Pausing is previewed (audit).** `pause_automation` needs the preview and the yes, like the other automation changes. Editing a draft post stays immediate; only a scheduled post needs a preview.
- **The team is emailed (audit, 01-design.md §6.7).** `ai_post_change` and `ai_automation_change` are emailed to owners and admins as well as shown in the app. Each of them can turn the emails off in Settings › Notifications (`notification_prefs.email_ai_changes`, on by default, no migration).
- **Ask says what it reads (audit).** The `ask` permission's words on the consent screen and the key page say that Ask can read anything the member can see, the inbox included, and uses AI credits.
- **Activity for keys.** `GET /v1/w/{wid}/api-keys/{key_id}/activity` returns a key's latest 50 tool calls, and Settings › MCP & API shows them under the key (owners and admins).
- **The tool list is generated.** `apps/api/scripts/export_mcp_tools.py` writes `apps/web/src/lib/marketing/mcp-tools.json`; `tests/unit/test_mcp_tool_reference.py` fails when it is stale.
- **The key limit holds under load.** Creating a key takes the workspace's `api_keys` limit lock before counting, so two creations at once can't pass 20.
