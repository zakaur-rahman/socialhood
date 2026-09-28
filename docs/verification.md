# Platform verification (T0.9)

Every "verify at build time" item in the spec, answered from current provider docs **and** a real
test account where one is needed. Record the answer, the source link and the date, then correct
`BUILD_SPEC.html` if it was wrong. Must be complete before P2.

Status: **not started**. It needs accounts that only the business can create: a Meta developer
app with Instagram test users and a WhatsApp test number, a Dodo test account, and a paid-tier
Gemini key.

| # | Item | Spec | How to check | Answer and source | Date |
|---|------|------|--------------|-------------------|------|
| 1 | Which secret signs Instagram webhooks (Instagram app secret or Meta app secret) | TR-WH-02 | Trigger a webhook on a test account; verify `X-Hub-Signature-256` against each secret | | |
| 2 | Comment webhook payload shape (`value.id` vs `comment_id`, `changes[]`, `parent_id`) and whether API-posted replies trigger `comments` | TR-WH-04, F-12 | Comment and reply on a test post; capture raw payloads into `tests/fixtures/meta/` | | |
| 3 | Accepted `subscribed_fields` names; whether echoes need `message_echoes` | TR-PL table | `POST /me/subscribed_apps` with each field; send from the Instagram app | | |
| 4 | Private reply rules: permission needed, second reply error, error after 7 days | TR-PL-04, FR-AUT-10 | Private-reply twice to one comment; to a comment older than 7 days | | |
| 5 | IGSID is the same across comment `from.id`, DM sender and private-reply recipient | F-06, F-12 | Compare ids from one test user's comment, DM and private reply | | |
| 6 | `content_publishing_limit.quota_total` (50 or 100); feed video vs Reels | FR-PUB-05 | Call the endpoint on a test account; publish a video | | |
| 7 | Conversations API history on connect: how far back, which fields | FR-CON-01 | Connect an account with existing threads | | |
| 8 | Echo format for messages sent in the Instagram app and by other tools | F-06 step 3 | Reply from the Instagram app; capture the echo | | |
| 9 | Human Agent tag request syntax and eligibility (after approval) | TR-PL-04 | Send with `MESSAGE_TAG` / `HUMAN_AGENT` between 24 h and 7 days | | |
| 10 | Instagram button template limits (text length, buttons, URL rules) | FR-AUT-13 | Send a button template DM to a test user | | |
| 11 | 2025+ insights metric names (`views` etc.) and availability with Instagram Login | FR-ANL-01 | Call media and account insights on a test account | | |
| 12 | `X-Business-Use-Case-Usage` present on `graph.instagram.com` | TR-PL-09 | Inspect response headers | | |
| 13 | Deauthorize and data-deletion payloads and their signing secret | TR-WH-02 | Remove the app from a test account; request deletion | | |
| 14 | WhatsApp Embedded Signup v4 session-info event format | FR-CON-02, F-04 | Complete Embedded Signup in a test business | | |
| 15 | WhatsApp template send format; error codes 131047 and 131026 | TR-PL-03 | Send a template; send outside the window; send to an invalid number | | |
| 16 | Dodo checkout fields, customer portal endpoint, merchant of record | TR-BIL-01, TR-BIL-06 | Dodo test account and docs | | |
| 17 | Gemini model ids; `response_format` and `thinking_level` in the Python SDK; Embedding 2 task-prefix format | TR-AI-02, TR-AI-03 | Call each model with the SDK version in `uv.lock` | | |
| 18 | `graph.instagram.com` accepts the token as `Authorization: Bearer` (the adapter never puts it in the URL) | TR-PL-05 | Call `/me` with the header only | | |
| 19 | Code-exchange response shape (`data[]` or flat) and the `permissions` format | F-03 | Complete Instagram Login on a test account; record the response in `tests/fixtures/meta/` | | |
| 20 | `/me` `user_id` equals the webhook `entry.id` (routing depends on it), and `id` is the app-scoped id the deauthorize callback sends | TR-WH-05, F-16 | Compare `/me` with a webhook and a deauthorize payload | | |
| 21 | Long-lived token refresh: minimum age (24 h) and the new `expires_in` | FR-CON-05 | Refresh a day-old token | | |
