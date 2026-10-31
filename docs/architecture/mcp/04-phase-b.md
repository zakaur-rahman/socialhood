# 04 · MCP server: phase B (writes, media uploads, Ask)

- **Status:** built on `feature/mcp-b` (from `feature/mcp-core`), 2026-11-01. Deviations and small calls: "C-165 (phase B)" in `docs/CONFLICTS.md`.
- **Design:** [01-design.md](01-design.md), decisions [02-decisions.md](02-decisions.md), phase A [03-phase-a.md](03-phase-a.md).
- **Result:** the catalogue is now the design's 25 tools (13 read, 12 new).

## The 12 new tools

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
| `resume_automation` | `automations:write` | admin | write | Pro, Max | false / false / true / true |
| `ask_amplychat` | `ask` | agent | read | all (the plan's AI credits, D8) | true / false / true / false |
| `get_ask_answer` | `ask` | agent | read | all | true / false / true / false |

`get_media_upload` (phase A) reads the tickets these tools make. Every write takes an `idempotency_key`. `create_post` and `add_knowledge` also dedupe an identical resend for 10 minutes. `pause_automation` and `resume_automation` don't: they undo each other, so a replay would swallow a real second pause.

### The prompts

`schedule_a_post` and `weekly_inbox_digest` (`mcp/prompts.py`), listed by `prompts/list`. The first walks the member through accounts, media, caption and time, previews with `create_post`, and schedules only after a yes.

## Posts: direct, with safety nets (D3)

1. **Confirmation.** `create_post` (to schedule), `update_post` (on a scheduled post, or giving a draft a time) and `cancel_post` (of a scheduled post) change nothing until called again with `confirmed: true`. The first call returns a **preview** (`preview: true`, `post_id` null for a post not yet created): the resolved time in the workspace zone and UTC, the accounts, and the composer's checklist. The preview runs the real flow inside a savepoint and rolls it back, so its errors are the real errors. A preview is never stored for replay, so the same `idempotency_key` can then do the real thing. Saving a draft needs no confirmation.
2. **Five minutes ahead.** `when` earlier than now + 5 minutes (`MIN_SCHEDULE_LEAD`) is a field error on `when`. There is no "publish now".
3. **The team is told.** A scheduled, changed or cancelled post notifies the owners and admins (in the app, `ai_post_change`) with the AI app, the member and a link to the post, where it is cancelled.
4. **Free saves drafts only.** `create_post` is a draft-tier tool, so Free (mode capped at `read_drafts`) can call it with `when: "draft"`; any other `when` is `entitlement_required` (`ai_connections`). A Pro workspace set to "read and drafts" gets a plain refusal instead.
5. **Daily cap.** `mcp_posts_daily`: Pro 25, Max 100, counted when a post is scheduled.

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
- **Caps.** Per workspace per UTC day: files `mcp_uploads_daily` (Free 20, Pro 200, Max 1,000) and megabytes `mcp_upload_mb_daily` (500, 10,000, 50,000). Counted when a file finishes; a new ticket is refused once the day is used up.

## Drafts, knowledge, automations, Ask

- **`draft_reply`** saves the text (or a draft Amplychat writes from the knowledge base, 2 AI credits) as the conversation's pending reply suggestion, answering the customer's latest message. The inbox shows it like any suggestion. It never sends and there is no send tool. A closed reply window is refused.
- **`add_knowledge`** adds a note or FAQ through `services/knowledge/sources.create`; the plan's characters-of-knowledge limit applies (402). Ingestion is queued after the commit.
- **`resume_automation`** only resumes an automation that was live before (`activated_at` set); a never-live draft is refused with a link. It runs the app's own activation (validation, plan limit) and restarts a held private-reply queue.
- **`ask_amplychat`** creates a normal Ask run (`agent_runs.create`, the `ai` rate limit, the plan's credits), commits, enqueues it for the worker, and waits up to 25 seconds. Longer runs return `ask_run_id` for `get_ask_answer`. The same question twice in two minutes by one connection is the same run.

## Plumbing

- `ToolCall` gained `note(...)` (a line for `audit_events`), `after_commit` (work for after the commit) and `client_name`.
- **Audit mirror.** After a write commits, `calls._run` writes each noted line to `audit_events` ("Asha via Claude Code"). It sits next to phase A's `mcp_tool_calls` row, which is still written for every call. A failing mirror is logged, never fails the call.
- Writes now commit with `events.commit_and_publish`, so the app's live updates (`scheduled_post.updated`, suggestions) reach open browsers.
- New entitlements (`billing/plans.py`): `mcp_posts_daily`, `mcp_uploads_daily`, `mcp_upload_mb_daily`. `plan-table.json` is regenerated.
- New routes for the upload page: `GET /v1/w/{wid}/mcp-uploads/{id}` (the ticket and its signed fields) and `POST …/complete` (owners and admins). `openapi.json` and `schema.d.ts` are regenerated.

## Example: edit a video in Claude Code with ffmpeg, upload it, schedule the Reel

Setup once: a Pro workspace, an API key with `posts:read`, `posts:write` and `media:write`, and `claude mcp add --transport http amplychat https://api.amplychat.com/mcp --header "Authorization: Bearer $AMPLYCHAT_API_KEY"`.

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
