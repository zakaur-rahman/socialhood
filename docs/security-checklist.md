# Security checklist (T9.2)

The security pass over SEC-01…SEC-14 (§2.12), every row of §0.3, and the rate limits (TR-API-07).
Branch `p9/security`, from `t/p9-launch` at 583fa50, checked on 2026-09-30.

Status values:
- **pass**: already met; the evidence proves it.
- **fixed**: met after a change on this branch.
- **gap**: not met. The fix is given, or the reason it is deferred.
- **accepted**: a known residual risk, with the reason it is accepted.

Paths are relative to `apps/api/src/socialhood/` (API), `apps/api/tests/` (tests) or `apps/web/`
(web), unless they say otherwise. Line numbers are at this branch's head.

## Summary

| Status | Count |
|---|---|
| pass | 28 |
| fixed | 7 |
| gap | 0 |
| accepted | 4 |

The 39 items are the 14 SEC items, the 16 §0.3 rows, the rate limits and the 8 extra checks at
the end. SEC-04, SEC-08, SEC-11 and SEC-14 count as fixed. The rate limits, X-1 and X-3 are the
other three fixes.

The one gap this pass found, **X-1, OAuth login CSRF on Instagram connect**, was fixed in the P9
integration pass (branch `p9/integration`, C-060). So were the fixes it needed in other agents'
files: uvicorn's `--no-server-header` (SEC-11), the client IP behind Render's proxy (rate limits)
and the `code=` log fields (SEC-07).

## SEC items (§2.12)

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| SEC-01 | No cross-workspace access | pass | See the SEC-01 notes below. |
| SEC-02 | No secrets in responses | pass | See the SEC-02 notes below. |
| SEC-03 | Tokens encrypted at rest; rotation | pass | See the SEC-03 notes below. |
| SEC-04 | Webhooks fail closed | fixed | See the SEC-04 notes below. |
| SEC-05 | CORS: exact origins, no credentials | pass | See the SEC-05 notes below. |
| SEC-06 | Secrets only from env; gitleaks | pass | See the SEC-06 notes below. |
| SEC-07 | Log redaction | pass | See the SEC-07 notes below. |
| SEC-08 | Input limits; no user HTML | fixed | See the SEC-08 notes below. |
| SEC-09 | SSRF protection | pass (accepted: A-1) | See the SEC-09 notes below. |
| SEC-10 | Prompt injection containment | pass | See the SEC-10 notes below. |
| SEC-11 | Headers | fixed | See the SEC-11 notes below. |
| SEC-12 | Operational endpoints | pass (`/metrics` is T9.3) | See the SEC-12 notes below. |
| SEC-13 | Dependency audits | pass | See the SEC-13 notes below. |
| SEC-14 | No dev features in production | fixed | See the SEC-14 notes below. |

### SEC-01: no cross-workspace access
- **Resolving the workspace.** `auth/deps.py:101-120` `workspace_ctx` loads the caller's membership for the `{wid}` in the path. Anything else is 404, never 403.
- **Automatic filter.** `db/tenancy.py:60-95` adds the workspace filter to every query that touches a tenant table and stamps new rows.
- **Lint rule.** `scripts/check_tenancy.py` passes ("Tenancy rules: OK").
- **Tests.** In `tests/tenancy/test_isolation.py`:
  - `test_every_route_with_a_path_id_hides_other_workspaces` (:475) walks every route.
  - `test_a_new_route_without_seed_data_fails_the_suite` (:511).
  - `test_user_level_routes_only_list_the_callers_workspaces` (:529).
  - The unit and tenancy suites pass: 1043 tests.

### SEC-02: no secrets in responses
- `tests/unit/test_schema_security.py::test_no_schema_property_looks_like_a_credential` fails on any response property that matches `token|secret|password|_enc$`. Only `token_expires_at` is allowed.
- `UploadSignature` returns a Cloudinary `signature` and `api_key` by design. Both are public values.

### SEC-03: tokens encrypted at rest, and rotation
- **Encryption.** `security/crypto.py:11,23` builds a `MultiFernet` from `TOKEN_ENCRYPTION_KEYS`. The first key encrypts and every key decrypts.
- **Rotation.** `security/rotate.py:25-45` re-encrypts `social_accounts.access_token_enc` and `whatsapp_pin_enc`.
- **Tests.**
  - In `tests/unit/test_security_primitives.py`: `test_a_token_round_trips_and_is_not_stored_in_clear` (:17), `test_rotation_keeps_old_tokens_readable_and_moves_them_to_the_new_key` (:24) and `test_a_missing_or_malformed_key_fails_at_startup` (:37).
  - `tests/integration/test_account_upkeep.py::test_key_rotation_re_encrypts_every_token`.

### SEC-04: webhooks fail closed
- **Startup.** `settings.py` `REQUIRED_IN_PRODUCTION` lists every webhook secret: Clerk, Instagram app secret and verify token, Meta app secret, WhatsApp verify token and Dodo. Outside production, a route without its secret answers 503.
- **Signature checks.** All run on the raw bytes, in constant time:
  - `security/signatures.py`
  - `webhooks/instagram.py:33-62`, `whatsapp.py`, `dodo.py:53`, `clerk.py:41-47` and `meta_privacy.py`
- **Existing tests** cover valid, invalid, missing and replayed signatures:
  - `test_instagram_webhook.py:82`, `test_whatsapp_webhook.py:183`, `test_clerk_webhook.py:68`
  - `test_billing_webhooks.py:436,457,505`, `test_privacy_and_sandbox.py:70`
  - `unit/test_standard_webhooks.py`
- **Fixed.** A Clerk delivery with a malformed `svix-signature` (bad base64) made svix raise `binascii.Error`. The route answered **500** instead of 401. It never stored anything, but it did log an unhandled error.
  - `webhooks/clerk.py` now refuses any verification failure with 401.
  - New test: `tests/integration/test_security_pass.py::test_every_webhook_refuses_an_unsigned_or_forged_delivery`. It tries 8 unsigned or forged deliveries across the 4 providers.
  - New test: `test_the_subscription_challenge_needs_the_verify_token`. It checks the Instagram and WhatsApp GET verify, and that the challenge is not reflected.
- **Cloudinary** has no inbound webhook, so there is nothing to verify. Its only signing is the outgoing upload signature (see A-3).

### SEC-05: CORS
- `main.py:69-77`: `allow_origins=settings.cors_allowed_origins` (exact matches) and `allow_credentials=False`.
- New test: `test_security_pass.py::test_cors_allows_only_the_configured_origin_without_credentials`. It checks that the allowed origin is echoed, and that a look-alike origin, `null` or another origin gets no `Access-Control-Allow-Origin`.

### SEC-06: secrets handling
- **Environment only.** Settings come only from the environment (`settings.py`).
- **No hard-coded fallbacks.** `unit/test_settings.py::test_connection_urls_have_no_fallback`.
- **Git.** `.gitignore` covers `.env` and `.env.*`, except `.env.example`. `git ls-files` shows only the two `.env.example` files.
- **Build output.** `next.config.ts` has no `output: "standalone"`. Next.js inlines only `NEXT_PUBLIC_*` values.
- **CI.** The `secrets` job runs gitleaks on every push (`.github/workflows/ci.yml`).
- **Full-history scan.** gitleaks on a mirror of every ref reported "75 commits scanned … no leaks found". It used the repo's `.gitleaksignore`, which has one known false positive.

### SEC-07: log redaction
- **Rules.** `observability/logging.py`:
  - :21 redacts keys matching `token|secret|authorization|password|signature|(^|_)code$`.
  - :40 cuts `text` and `body` to 40 characters at INFO.
  - :83 holds httpx and httpcore at WARNING (C-010).
- **Tests.** `unit/test_logging.py` :10, :30, :35 and :43.
- **Note.** Redacting keys named `code` also blanked 13 diagnostic `code=error.code` log fields (captions, knowledge, analysis, summaries, planner). The integration pass renamed them to `error_code`, which is on the safe list, and `unit/test_logging.py::test_no_log_call_names_a_diagnostic_code_field_the_redaction_blanks` fails on any new one.

### SEC-08: input limits
- **Body size.**
  - `api/middleware.py` `BodyLimitMiddleware`: 1 MB for the API, 5 MB for webhooks. It checks Content-Length and also counts streamed bytes.
  - Tests: `test_instagram_webhook.py:107`, `:116`.
- **Fixed: chunked bodies.** A chunked body over the limit on a JSON route got **400**, not 413. FastAPI's body parser turned the middleware's exception into "error parsing the body". The body was still refused and memory stayed bounded.
  - `_BodyTooLarge` is now an `HTTPException(413)`, which FastAPI re-raises.
  - New test: `test_security_pass.py::test_a_chunked_body_over_the_limit_is_refused`.
- **Fixed: string lengths.** 4 request strings had no maximum length:
  - `TemplateSend.params[]` (now 1024)
  - `AutomationDefinition.keywords[]` (500; the service still enforces 100)
  - `AutomationDefinition.public_reply_texts[]` (2000; the service still enforces 300)
  - the `status` query on `GET …/knowledge-gaps` (16)
  - New test: `unit/test_schema_security.py::test_every_request_string_has_a_maximum_length`. It walks every body, query, path and header parameter in the OpenAPI document. A string must have a `maxLength` or be an enum, a const, a uuid or a date.
  - Hidden routes are bounded by hand: the OAuth callback (`code` ≤2048, `state` ≤128) and the webhooks (by body size).
- **User content is never HTML.**
  - The web has no `dangerouslySetInnerHTML`, no `innerHTML` and no markdown library.
  - Agent answers use a React-only subset parser (`src/lib/agent/answer.ts`, `src/components/agent/AnswerText.tsx`).
  - Messages and comments render as text nodes.
  - New tests in `src/lib/security/security.test.tsx`: an `<img onerror>`, `<script>` or `javascript:` payload renders as text in an Ask Social Hood answer and in a customer message.
  - Existing test: `src/lib/agent/answer.test.ts:35`.

### SEC-09: SSRF protection
- **The guard.** `security/ssrf.py` does the following:
  - allows http and https only;
  - rejects userinfo;
  - checks literal IPs before anything else;
  - resolves DNS and rejects any private, loopback, link-local, metadata, multicast, reserved or unspecified address, including IPv4 inside IPv6 (mapped, 6to4, teredo);
  - connects to the checked IP with the real Host header and SNI, which stops DNS rebinding;
  - follows at most 3 redirects, re-checking each one;
  - has a 15 s total timeout;
  - caps the body at 2 MB;
  - accepts HTML only.
- **Tests.**
  - `unit/test_ssrf.py`: 13 tests, including the metadata IP, private redirects, 3 redirects and 2 MB.
  - `integration/test_knowledge.py:270` (`test_a_page_on_a_private_network_fails_without_a_request`).
- **Push endpoints.** Allowlisted push services, https on port 443 only. See `notify/push_webpush.py:39-58`, checked both on register and on send. Tests: `contract/test_web_push.py:68,152` and `integration/test_notification_settings_api.py:172`.
- **Media URLs sent to Meta** always come from stored Cloudinary assets. No client-supplied URL reaches a platform.
- **Instagram inbound media download** does not use the guard. See A-1.

### SEC-10: prompt injection containment
- **Placeholders.** `ai/prompts.py` fills them from trusted settings only. Customer and knowledge text go in the message contents (`agent/context.py:1-15`).
- **Auto replies.** They pass the policy (`ai/policy.py`) and the output filter. The filter blocks replies over 1000 characters, and any link, email or phone number that is not in the allowed sources (`ai/output_filter.py:101-143`).
- **Tests.** `unit/test_ai_policy.py:225,236`.
- **Ask Social Hood (C-033)** is R1 read-only:
  - `agent/registry.py:176-182` refuses any write-tier tool in R1.
  - The tools are 23 read and 4 draft; none writes.
  - `agent/gateway.py` `decide()` is an R2 stub that nothing calls.
- **Tests for the agent.**
  - In `unit/test_agent_contract.py`: `test_the_registry_refuses_specs_that_break_the_rules` (:211) and `test_the_shipped_tools_are_read_or_draft` (:249).
  - `unit/test_agent_tools_registry.py:56`.
  - `integration/test_agent_tools_inbox.py:201` (`…draft_reply…sends_nothing`).
  - `integration/test_agent_runtime.py:182` (the requester's role bounds the tools).

### SEC-11: headers
- **API.** `api/middleware.py:20-25` adds HSTS, `nosniff`, `Referrer-Policy: no-referrer` and `CSP: frame-ancestors 'none'` to every response, including 500s. Tests: `unit/test_problems.py:74`, `:84`.
- **Fixed: web.** The web had no page CSP and no security headers; the only rule was `/sw.js`'s CSP.
  - `src/lib/security/headers.ts`, wired in `next.config.ts`, now sets on every route:
    - a CSP (below);
    - HSTS;
    - `X-Content-Type-Options: nosniff`;
    - `X-Frame-Options: DENY`;
    - `Referrer-Policy: strict-origin-when-cross-origin`;
    - `Permissions-Policy` (camera, microphone, geolocation, payment and usb off);
    - `COOP: same-origin-allow-popups`, which Meta's signup popup needs.
  - The CSP allows only:
    - the app itself;
    - the API origin (`NEXT_PUBLIC_API_BASE_URL`);
    - Clerk: the Frontend API host decoded from the publishable key, `img.clerk.com`, Turnstile, `*.protect.clerk.com` and telemetry;
    - Cloudinary: `api.cloudinary.com` for uploads, `res.cloudinary.com` for delivery;
    - Instagram and Facebook CDNs, for images and media only;
    - Meta's SDK: `connect.facebook.net`, and `*.facebook.com` for frames and connect;
    - Sentry: the origin of `NEXT_PUBLIC_SENTRY_DSN`'s ingest host, for example `https://o42.ingest.us.sentry.io`. A Sentry `tunnelRoute` would be covered by `'self'`.
  - The API origin comes from the build's `NEXT_PUBLIC_API_BASE_URL`, so the Playwright run (web :3100, API :8100) gets `http://localhost:8100`. The Clerk host is decoded from the publishable key, which also covers Clerk testing tokens.
  - The CSP also sets `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'` and `form-action 'self'`. It adds `upgrade-insecure-requests` when the API is https.
  - Tests: `src/lib/security/security.test.tsx` ("the web CSP").
  - Checked with `next build` and `next start`, then `curl -D -` on `/`, `/sw.js` and `/w/acme/settings/connections`. Every header was present, and `/sw.js` keeps its own stricter CSP.
  - Headless Chromium loaded `/sign-in` and `/unsubscribe` with the CSP. Clerk rendered the sign-in form, and the console showed no CSP violations.
- **Accepted (A-4):** `script-src 'unsafe-inline'`, and Meta's SDK allowed app-wide.
- **Infra (done in the integration pass):** uvicorn sends `server: uvicorn` unless it is started with `--no-server-header`, which the app cannot change. Both API start commands in `infra/render.yaml` now pass it.

### SEC-12: operational endpoints
- **`/healthz`** returns `{"status":"ok"}` only (`api/health.py:31`).
- **`/readyz`** needs the bearer `METRICS_TOKEN` outside local and test environments, and is 404 otherwise (`api/health.py:36-45`).
- **`/docs` and `/openapi.json`** are off in production (`main.py:47-49`). They stay on in staging.
- **`/metrics`** is T9.3 (agent C). The integrator should confirm its bearer check.

### SEC-13: dependencies
- **CI.** `ci.yml` runs pip-audit on the exported lock and `pnpm audit --prod --audit-level high`. Dependabot runs weekly (`.github/dependabot.yml`).
- **This pass.**
  - pip-audit: "No known vulnerabilities found".
  - `pnpm audit --prod`: 2 moderate, no high and no critical. Both are transitive through `@clerk/ui` → `@solana/*` → `jayson`: `uuid@8.3.2` (GHSA-w5hq-g745-h8pq) and `stream-json@1.9.1` (GHSA-528h-pc64-c93x). Neither runs in our code path, and CI's high threshold passes. They are left for Clerk's next release rather than overridden.

### SEC-14: no dev features in production
- **Refusals.** The production validator (`settings.py` `_production_rules`) refuses:
  - `SANDBOX_PLATFORM_ENABLED`;
  - `LOG_LEVEL=DEBUG`;
  - the fake Dodo, email and push providers;
  - any missing required variable.
- **Sandbox routes** are 404 when disabled (`api/v1/accounts.py:102-104`). Test: `test_privacy_and_sandbox.py:193`.
- **Fixed.**
  - `AI_PROVIDER=fake` was allowed in production. It is now refused.
  - The new `RATE_LIMITS_ENABLED=false` is refused in production.
  - `CLIENT_IP_HEADER` is required in production.
  - Tests: `unit/test_settings.py::test_production_refuses_fake_providers[ai_provider|dodo|email|push]` and `::test_production_refuses_disabled_rate_limits`.

## §0.3: what v1 teaches

| # | v1 defect | v2 rule | Status | Evidence |
|---|---|---|---|---|
| 1 | Automation endpoints had no owner check; tokens leaked | SEC-01, SEC-02, TR-TEN | pass | The tenancy suite walks every route with a path id (SEC-01). The schema scan covers tokens (SEC-02). |
| 2 | Keywords matched across tenants; "keyword contains comment" | FR-AUT-06 | pass | Matching is per workspace under the tenant filter. `unit/test_automation_matching.py:82` (`test_keyword_matching`, word vs contains), `:46` (normalisation) |
| 3 | Dodo skipped the signature when the secret was unset, and verified a re-serialised body | SEC-04, TR-WH-02 | pass | `webhooks/dodo.py:53` checks the raw bytes and fails closed (503 unset, 401 bad). `test_billing_webhooks.py:457` (`…unsigned_event_is_refused_and_grants_nothing`), `:505` (`test_no_path_but_a_signed_event_grants_pro`) |
| 4 | LinkedIn verification commented out; Instagram GET verify ignored the token | SEC-04 | pass | `webhooks/instagram.py:33-48` compares the verify token in constant time. There is no LinkedIn route in R1. New: `test_security_pass.py::test_the_subscription_challenge_needs_the_verify_token` |
| 5 | Gemini options at the top level were ignored | TR-AI-03 | pass | `unit/test_gemini_provider.py:139` (`test_every_option_is_inside_the_config`), `:162` |
| 6 | No event store; check-then-insert; processing inside the request | TR-WH-01…05 | pass | `webhook_events` has a unique (provider, dedupe_key) (`models/platform.py:67`). Intake stores, then enqueues. `test_instagram_webhook.py:63` (`…stored_once_per_event_and_queued`) |
| 7 | SSE clients in memory; crons in every process | TR-RT-01, TR-JOB-02 | pass | SSE reads Valkey streams (`realtime/stream.py`); jobs run on Procrastinate workers. `test_realtime_stream.py:73-94`, `test_jobs.py` |
| 8 | Send returned 201 when the platform refused; attachments dropped | FR-INB-07…09 | pass | 202 with the message queued; status arrives over SSE. `test_sending.py:69`, `test_sending_media.py`, `test_ingest.py` |
| 9 | 24 h and 7-day windows never checked; no HUMAN_AGENT tag | FR-INB-10, TR-PL-04 | pass | `services/reply_window.py`. `unit/test_reply_window.py:27-39`, `contract/test_instagram_send.py:65` (HUMAN_AGENT) |
| 10 | Retries exited early; wrong Instagram video edge | FR-PUB-05, TR-JOB-04 | pass | `jobs/retry.py`; C-008. `unit/test_retry_and_cron.py:52`, `contract/test_instagram_publishing.py` |
| 11 | Plan limits never enforced; free trials | FR-BIL-*, D9 | pass | `billing/entitlements.py`. `test_entitlements.py`, `test_billing_lifecycle.py`, `test_read_only_accounts.py` |
| 12 | Clerk API call and a DB write on every request | TR-AUTH-02 | pass | `auth/clerk.py` verifies the JWT locally with RS256 only. Clerk is fetched once per user; last_seen is written at most every 15 minutes (`auth/deps.py`). `test_auth.py`. New: `test_security_pass.py` (alg none, HS256 key confusion, wrong issuer or azp → 401) |
| 13 | No platform token refresh | FR-CON-05 | pass | `test_account_upkeep.py:47-115` |
| 14 | `.env` in build output; tokens and codes in logs; hard-coded Redis URL | SEC-06, SEC-07 | pass | See SEC-06 and SEC-07. `test_settings.py:33` (no fallback URL) |
| 15 | Frontend: 8 API clients, cookie-only auth across domains, … | UX-TOK-*, TR-FE-* | pass (security part) | One client, `src/lib/api/client.ts`, with a bearer token per request. API auth never uses cookies, so no CSRF on the API. |
| 16 | Static replies stored as customer messages; scheduled mixed into messages | data model | pass | `messages.direction`; a separate `scheduled_messages` table (C-020) |

## Rate limits (TR-API-07, §2.12)

Status: **fixed**. Nothing was implemented before this pass: `rate_limited` existed only as an
error code.

| Limit | Key | Where | Routes |
|---|---|---|---|
| 300/min | per user (Clerk id) | `auth/deps.current_user`, before any database work | every signed-in route |
| 60/min | per workspace | `api/ratelimit.SENDS` | send message, retry, comment reply, private reply, create scheduled message, publish now |
| 20/min | per workspace | `api/ratelimit.AI` | regenerate suggestion, conversation summary, caption, hashtags, knowledge test, agent run, post summary |
| 30/min | per IP | `api/ratelimit.OAUTH_CALLBACK` | `GET /v1/oauth/instagram/callback` |
| 60/min | per IP | `api/ratelimit.PUBLIC` | `POST /v1/digest/unsubscribe`, `GET /v1/billing/plans`, `GET /v1/data-deletion/{code}` |
| none | n/a | n/a | `/webhooks/*`: not limited by IP, because Meta shares IPs; bodies are capped at 5 MB instead |

**Mechanism.** `security/ratelimit.py` keeps a Valkey sorted-set sliding window, trimmed, counted
and recorded in one Lua call. The rules:
- A refused request is not recorded.
- Over the limit, the answer is `429` problem+json with code `rate_limited` and `Retry-After`, the whole seconds until the oldest request leaves the window.
- A Valkey outage lets requests through, with a warning log.

**Workspace limits.** These resolve the same cached `workspace_ctx` first. A caller who is not a
member gets 404 and spends nothing from that workspace's budget.

**Client IP.** Taken from `CLIENT_IP_HEADER`, which is `x-forwarded-for` on Render (integration
pass, C-060). Render documents no other client-IP header; `true-client-ip` was an assumption about
Cloudflare that Render doesn't promise. `security/client_ip.py` reads the list from the right and
takes the first entry that isn't a proxy (Cloudflare's published ranges, private and shared
ranges): the rightmost untrusted hop. A client's own entries stay on the left, so it can't choose
its key. X-Forwarded-For's first entry, which uvicorn uses with `--forwarded-allow-ips="*"`, is
never used. Tests: `unit/test_client_ip.py` (layouts, spoofed prefixes, ports, IPv6, garbage) and
`test_rate_limits.py::test_behind_render_the_client_ip_is_the_rightmost_untrusted_hop`. The
staging check is in `docs/ops/deploy.md` section 7.

**Tests.** `tests/integration/test_rate_limits.py`, 28 tests:
- the window arithmetic;
- the per-user limit, and that an invalid token spends nothing;
- every send and AI route (13 parametrized);
- that the budgets are separate, and that outsiders spend nothing;
- 31 OAuth callbacks, where the 31st is a 429;
- each public route;
- that the edge header wins over a spoofed X-Forwarded-For;
- that webhooks are never limited;
- that every `/v1` route sits behind a limit (it walks the route dependencies);
- the switch, and a Valkey outage.

The 429 is covered by each operation's documented `default` problem response. No per-operation
429 entries were added, so the contract changes only for SEC-08.

## Extra checks

| ID | Check | Status | Evidence |
|---|---|---|---|
| X-1 | OAuth state bound to the browser (login CSRF on Instagram connect) | fixed | See X-1 below. |
| X-2 | Open redirects: the OAuth callback, checkout return and the auth return | pass | See X-2 below. |
| X-3 | Navigation to URLs the API returns (checkout, portal, Instagram authorize) | fixed | See X-3 below. |
| X-4 | Idempotency (TR-API-05) | pass, with notes | See X-4 below. |
| A-1 | Instagram inbound media download is not behind `security/ssrf.py` | accepted | See A-1 below. |
| A-2 | WhatsApp media: the bearer token is sent to the URL Graph returns | accepted | See A-2 below. |
| A-3 | The Cloudinary upload signature signs only `folder` and `timestamp` | accepted | See A-3 below. |
| A-4 | Web CSP keeps `script-src 'unsafe-inline'`; Meta's SDK is allowed app-wide | accepted | See A-4 below. |

### X-1: OAuth login CSRF on Instagram connect (fixed)
**The problem.** The state is random, single-use, lasts 10 minutes and names the starting user and
workspace (`services/connections.py` `start_instagram_connect`). The public callback, however,
completed the connect for whichever browser brought the code.

**The attack.** An attacker starts a connect in their own workspace and sends the Instagram
authorize link to a victim. If the victim approves "Social Hood", the victim's Instagram account is
connected to the attacker's workspace, which can then read and send its DMs. F-04 (`account_in_use`)
blocks this only when the victim's account is already connected elsewhere.

**The fix (p9/integration).** The callback no longer connects anything:
1. `api/v1/oauth.py` pops the state, refuses a workspace that isn't active, and parks the code under
   a one-time nonce: `oauth:held:{nonce}` in Valkey, 10-minute TTL, holding the state's user and
   workspace and the code **encrypted** with `TOKEN_ENCRYPTION_KEYS` (`hold_instagram_code`). The
   code, not the token, is kept: it lives an hour at most, works once, and is useless without the
   app secret. Nothing is exchanged until the member confirms.
2. It redirects to `/w/{slug}/settings/connections?instagram=<nonce>`.
3. The signed-in Connections page posts the nonce once to `POST /v1/w/{wid}/social-accounts/instagram/complete` (Admin) and drops it from the URL.
4. `finish_instagram_connect` takes the nonce with `GETDEL` (single use, whatever happens next), then
   connects only if the stored user id and workspace id equal the caller's. `workspace_ctx` has
   already required a membership in an active workspace, and `Admin` the role.
- **Answers.** 404 `not_found` for an expired, used or unknown nonce ("That connection link
  expired."); 403 `forbidden` when someone else started it ("This Instagram connection was started
  by someone else, so it wasn't added."). The connect's own outcomes keep their codes: 409
  `account_in_use`, 402 `quota_exceeded` (`accounts_per_platform`, with the limit), the new 422
  `ig_not_professional`, and 502 `platform_error` when Instagram fails.
- **A victim** lands on the attacker's workspace URL. Not being a member, the page says "Workspace
  not found" and nothing is posted; posted to any workspace, the nonce is refused (403) and used up.
  The code is never exchanged.
- **Deletion (T9.6 follow-up).** The callback refuses a workspace that isn't active, and the
  complete re-reads the workspace row `FOR SHARE` before storing the account, so a deletion that
  starts mid-connect either waits and then disconnects the account, or wins and the connect is 404.
  The WhatsApp signup does the same (`repositories/workspaces.is_active`).
- **Tests** (`tests/integration/test_connections.py`):
  `test_a_victim_cannot_finish_an_attackers_connect`,
  `test_a_nonce_for_another_workspace_of_the_same_member_is_refused`, `test_a_nonce_works_once`,
  `test_an_expired_nonce_fails` (which also checks the code is stored encrypted),
  `test_no_connect_for_a_workspace_being_deleted`, and the existing connect tests through the new
  `tests/support/instagram.connect` helper (start, callback, complete). Web:
  `settings/connections/page.test.tsx` (the nonce is posted once and the copy for each refusal)
  and `lib/copy.test.ts`.

**WhatsApp Embedded Signup is not affected.** Meta's SDK runs in a popup opened by the signed-in
Connections page and hands the code back to that page's JavaScript (`src/lib/whatsapp/embedded-signup.ts`),
which posts it with the member's bearer token to `POST …/social-accounts/whatsapp/embedded-signup`.
There is no public redirect for another browser to land on, and the API never uses cookies, so a
code can only be submitted by the member whose page asked for it.

### X-2: open redirects (pass)
- **OAuth callback.** It redirects only to `WEB_BASE_URL` plus the stored slug, which must match `SLUG_PATTERN`. The `error` value maps to fixed codes (`api/v1/oauth.py`). New: `test_security_pass.py::test_the_oauth_callback_only_redirects_to_the_web_app`.
- **Checkout return.** The URL is `WEB_BASE_URL/w/{slug}/settings/billing?checkout=return`, with no client input (`services/billing.py:218-257`). Test: `test_billing_api.py:91`.
- **Auth return.** Clerk's `redirect_url` is limited to the app origin and `*.socialhood.com`. Clerk's default when `allowedRedirectOrigins` is unset is in `@clerk/shared` `internal/clerk-js/url.mjs:257-265`.
- **Service worker.** Push clicks open same-origin URLs only (`public/sw.js:22-29`).

### X-3: navigation to URLs the API returns (fixed)
- `src/lib/billing/browser.ts` `webUrl()` refuses anything but http(s), such as a `javascript:` or `data:` URL.
- It is used by checkout, the portal tab and now the Instagram connect (`src/app/(app)/w/[slug]/settings/connections/page.tsx`).
- Test: `security.test.tsx` ("leaving the app for a URL the API gave").

### X-4: idempotency (pass, with notes)
- **Required.** An Idempotency-Key is required on send, comment reply and private reply (`services/idempotency.py`; `test_sending.py:103-136`, `test_posts_comments_api.py:310`).
- **Optional** on creating a scheduled message.
- **Not taken** by retry and publish-now. Their state machines make a repeat harmless: retry returns a message that is already queued; publish-now is 409 unless the post is editable.

### A-1: Instagram inbound media download (accepted)
**Current state.** `platforms/instagram/reads.py:67-112` fetches with https only and follows
redirects.

**Why it is accepted.**
- The URL comes from a Meta-signed webhook, or from the Graph API over the account's token.
- Only media kinds that Meta itself hosts are downloaded: image, video, audio, file and sticker. Shares and stories are never fetched (`services/ingest.py:83`).
- Size (≤100 MB) and time (60 s) are capped.

**Follow-up.** Allow only Meta CDN hosts (`*.fbsbx.com`, `*.fbcdn.net`, `*.cdninstagram.com`),
and check public addresses on every hop, once live payloads confirm the hosts.

### A-2: WhatsApp media download (accepted)
The URL comes from Meta's Graph API (`platforms/whatsapp/graph.py:57-83`), which is trusted. The
shared client does not follow redirects.

### A-3: Cloudinary upload signature (accepted)
**Current state.** A member can upload any file into their own workspace's folder until the
signature's timestamp expires.

**Why it is accepted.**
- Registration reads the size and format back from Cloudinary and enforces the limits (`services/media_assets.py:151-234`).
- Unregistered files are never served by the app.
- The database also constrains `public_id` to the workspace folder (`models/media.py:71`).

**Follow-up.** Sign `allowed_formats` per purpose, and sweep unregistered uploads.

### A-4: web CSP (accepted)
**Inline scripts.** Next.js App Router bootstraps with inline scripts. A nonce would make every page
dynamic, and no path renders user or model HTML (SEC-08).

**Meta's SDK app-wide.** SEC-11 wants Meta's SDK on the Embedded Signup page only. A CSP belongs to
the document, and in-app navigations keep the document, so a Connections-only CSP would block the
SDK after client-side navigation. Only that page injects the script
(`src/lib/whatsapp/embedded-signup.ts`).

## Decisions made in this pass

1. **Webhooks are not IP-limited.** TR-API-07 says so, because Meta shares IPs. They keep the 5 MB cap. The meta privacy callbacks are webhooks too.
2. **Scheduled messages and publish-now count as sends.** TR-API-05 treats "send or schedule" alike.
3. **The AI class covers every model call a member can trigger.** That adds agent runs, conversation and post summaries, and hashtags to the spec's three examples.
4. **Public routes get 60/min per IP.** The OAuth callback keeps the spec's 30. The data-deletion page is server-rendered on Vercel, so its lookups share Vercel's IPs; 60/min is ample for it.
5. **"The checkout return" has no public API route.** The return lands on the signed-in billing page, which polls `GET …/billing` under the per-user limit.
6. **Limits fail open when Valkey is down.** This matches the idempotency and last-seen behaviour.
7. **`RATE_LIMITS_ENABLED` and `CLIENT_IP_HEADER` are new settings.** The first is refused as false in production. The second is required in production (`x-forwarded-for` on Render, read from the right; changed from `true-client-ip` in the integration pass).
8. **The web CSP comes from the build's `NEXT_PUBLIC_*` values.** These are the API URL, the Clerk publishable key and the Sentry DSN. `upgrade-insecure-requests` is added only when the API is https, so local production builds keep working.
9. **No explicit 429 in the OpenAPI document.** The `default` problem response already covers it, which avoids contract churn.
