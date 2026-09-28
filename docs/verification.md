# Platform verification (T0.9)

Every "verify at build time" item in the spec, answered from current provider docs **and** a real
test account where one is needed. Record the answer, the source link and the date, then correct
`BUILD_SPEC.html` if it was wrong. Must be complete before P2.

Status: **in progress** (items 1, 2, 3, 5, 8, 18, 20 and 21 partly or fully answered from a real account). It needs accounts that only the business can create: a Meta developer
app with Instagram test users and a WhatsApp test number, a Dodo test account, and a paid-tier
Gemini key.

| # | Item | Spec | How to check | Answer and source | Date |
|---|------|------|--------------|-------------------|------|
| 1 | Which secret signs Instagram webhooks (Instagram app secret or Meta app secret) | TR-WH-02 | Trigger a webhook on a test account; verify `X-Hub-Signature-256` against each secret | The **Instagram app secret**: `X-Hub-Signature-256` verified with `IG_APP_SECRET` (Meta also sends the SHA-1 `X-Hub-Signature`). Real DM and comment to @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 2 | Comment webhook payload shape (`value.id` vs `comment_id`, `changes[]`, `parent_id`) and whether API-posted replies trigger `comments` | TR-WH-04, F-12 | Comment and reply on a test post; capture raw payloads into `tests/fixtures/meta/` | Partly: comments come as `entry.changes[]` with `field: comments` and `value {id, text, from {id, username}, media {id, media_product_type}}`; no `verb` or `parent_id` on a top-level comment. `entry.time` is in seconds here but in milliseconds for `messaging`. Replies and API-posted replies still to check. Real DM and comment to @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 3 | Accepted `subscribed_fields` names; whether echoes need `message_echoes` | TR-PL table | `POST /me/subscribed_apps` with each field; send from the Instagram app | Partly: `POST /me/subscribed_apps` with `messages,messaging_seen,message_reactions,message_edit,comments` returned `success: true`. Echoes still to check. Real connect of @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 4 | Private reply rules: permission needed, second reply error, error after 7 days | TR-PL-04, FR-AUT-10 | Private-reply twice to one comment; to a comment older than 7 days | | |
| 5 | IGSID is the same across comment `from.id`, DM sender and private-reply recipient | F-06, F-12 | Compare ids from one test user's comment, DM and private reply | Partly: the commenter's `from.id` equals the DM `sender.id` (same IGSID). Private-reply recipient still to check. Real DM and comment to @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 6 | `content_publishing_limit.quota_total` (50 or 100); feed video vs Reels | FR-PUB-05 | Call the endpoint on a test account; publish a video | | |
| 7 | Conversations API history on connect: how far back, which fields | FR-CON-01 | Connect an account with existing threads | Partly: on a real account `GET /me/conversations?platform=instagram` then `/{conversation_id}?fields=messages{...}` returned 6 threads and 104 messages going back about 11 months, both directions (P3 backfill). Field details still to record. | 2026-09-29 |
| 8 | Echo format for messages sent in the Instagram app and by other tools | F-06 step 3 | Reply from the Instagram app; capture the echo | Partly: when the sender is itself a professional account subscribed to the app, Meta sends that account an `is_echo` message under its own `entry.id`, with a different `mid` (the mid embeds the account id) and the recipient as an app-scoped id. Echoes of our own sends still to check. Real DM and comment to @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 9 | Human Agent tag request syntax and eligibility (after approval) | TR-PL-04 | Send with `MESSAGE_TAG` / `HUMAN_AGENT` between 24 h and 7 days | | |
| 10 | Instagram button template limits (text length, buttons, URL rules) | FR-AUT-13 | Send a button template DM to a test user | | |
| 11 | 2025+ insights metric names (`views` etc.) and availability with Instagram Login | FR-ANL-01 | Call media and account insights on a test account | | |
| 12 | `X-Business-Use-Case-Usage` present on `graph.instagram.com` | TR-PL-09 | Inspect response headers | | |
| 13 | Deauthorize and data-deletion payloads and their signing secret | TR-WH-02 | Remove the app from a test account; request deletion | | |
| 14 | WhatsApp Embedded Signup v4 session-info event format | FR-CON-02, F-04 | Complete Embedded Signup in a test business | | |
| 15 | WhatsApp template send format; error codes 131047 and 131026 | TR-PL-03 | Send a template; send outside the window; send to an invalid number | | |
| 16 | Dodo checkout fields, customer portal endpoint, merchant of record | TR-BIL-01, TR-BIL-06 | Dodo test account and docs | | |
| 17 | Gemini model ids; `response_format` and `thinking_level` in the Python SDK; Embedding 2 task-prefix format | TR-AI-02, TR-AI-03 | Call each model with the SDK version in `uv.lock` | | |
| 18 | `graph.instagram.com` accepts the token as `Authorization: Bearer` (the adapter never puts it in the URL) | TR-PL-05 | Call `/me` with the header only | Yes: `/me` and `/me/subscribed_apps` succeeded with the token only in `Authorization: Bearer`. Real connect of @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 19 | Code-exchange response shape (`data[]` or flat) and the `permissions` format | F-03 | Complete Instagram Login on a test account; record the response in `tests/fixtures/meta/` | | |
| 20 | `/me` `user_id` equals the webhook `entry.id` (routing depends on it), and `id` is the app-scoped id the deauthorize callback sends | TR-WH-05, F-16 | Compare `/me` with a webhook and a deauthorize payload | Partly: webhook `entry.id` equals `/me` `user_id` (routing works). Deauthorize `user_id` still to check. Real DM and comment to @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 21 | Long-lived token refresh: minimum age (24 h) and the new `expires_in` | FR-CON-05 | Refresh a day-old token | New long-lived token came with `expires_in` of about 60 days (expiry 2026-11-27). Refresh at 24 h still to check. Real connect of @socialautomation5 via `pnpm tunnel` | 2026-09-28 |
| 22 | Instagram send API: `POST /{v}/me/messages` with `recipient.id`; response `{recipient_id, message_id}`; HUMAN_AGENT as `messaging_type: MESSAGE_TAG` + `tag: HUMAN_AGENT`; `sender_action: mark_seen`; image by URL (Cloudinary delivery URLs); one echo per attachment part | T3.6 | Send text, an image and a Human Agent reply from the app to a test user | | |
| 23 | Webhook shapes not yet seen: stickers, shared reels and posts, `is_deleted`, `is_unsupported`, postbacks, `reply_to.story`, the business's own reactions and seen events | T3.2 | Trigger each from a test account; record into `tests/fixtures/meta/` | | |
| 24 | Profile API: which users it refuses (code 230 "consent required" and 100/2534014 were both seen on a real account) | T3.3 | Fetch profiles of contacts who did and did not follow or message first | | |
| 25 | Cloudinary folder mode (fixed vs dynamic) keeps `ws/{id}/…` as the `public_id` prefix; the Admin API returns `duration` for videos | T3.3, T3.7 | Upload through the signed flow on the real cloud | | |
| 26 | WhatsApp: code exchange without `redirect_uri`, token expiry, phone number fields, `subscribed_apps`, number registration, webhook signing secret, status and media payloads, template send format, 131047 and 131026 on send vs as statuses, templates list fields | T3.12 | Complete Embedded Signup with a test number | | |
