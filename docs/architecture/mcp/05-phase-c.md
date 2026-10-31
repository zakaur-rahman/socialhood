# 05 · MCP server: phase C (OAuth, the consent page, Connected AI apps, the setup guide)

- **Status:** built on `feature/mcp-c` (from `feature/mcp-core`), 2026-11-01. Conflicts and small calls: "C-165 (phase C)" in `docs/CONFLICTS.md`.
- **Design:** [01-design.md](01-design.md) §3, decision D1 (our own small authorization server, login through Clerk). Phase A: [03-phase-a.md](03-phase-a.md).

## What was built

claude.ai and ChatGPT only connect through OAuth. Phase C adds an OAuth 2.1 authorization server inside the API, a consent page on the dashboard that uses the member's existing Clerk sign-in, OAuth access tokens on `/mcp`, the Settings page that lists and revokes connections, and the public setup guide.

### Endpoints

On the API's origin (`https://api.amplychat.com`, the issuer the protected resource metadata already named):

| Endpoint | What it does |
|---|---|
| `GET /.well-known/oauth-authorization-server` | RFC 8414 metadata: S256 only, `code` only, `none` / `client_secret_post` / `client_secret_basic`, `client_id_metadata_document_supported: true`, `authorization_response_iss_parameter_supported: true`, `offline_access` in `scopes_supported` |
| `GET /oauth/authorize` | Checks the request; 302 to the consent page, or back to the client with an OAuth error, `state` and `iss`. A bad `client_id` or `redirect_uri` is an HTML page for the person, never a redirect |
| `POST /oauth/token` | `authorization_code` (PKCE verifier, exact `redirect_uri`, `resource`) and `refresh_token` (rotation, reuse detection). `Cache-Control: no-store` |
| `POST /oauth/register` | Dynamic Client Registration (RFC 7591), for clients without CIMD |
| `POST /oauth/revoke` | RFC 7009. An access token alone; a refresh token revokes its whole connection. Always 200 |
| `GET /.well-known/oauth-protected-resource[/mcp]` | Phase A's RFC 9728 document, unchanged; its issuer now answers |

The consent page's API (Clerk session, in the OpenAPI document):

| Route | What it does |
|---|---|
| `GET /v1/connect/requests/{request_id}` | The waiting request: the app, where it goes back to, what it asked for in plain words, the member's workspaces and whether each can connect |
| `POST /v1/connect/requests/{request_id}/approve` | `{workspace_id, scopes}` → `{redirect_to}` (the app's redirect URI with `code`, `state`, `iss`) |
| `POST /v1/connect/requests/{request_id}/deny` | → `{redirect_to}` with `error=access_denied` |

Settings › Connected AI apps (Clerk session):

| Route | Who |
|---|---|
| `GET /v1/w/{wid}/ai-connections` | any member: owners and admins get everyone's, others their own; each with its scopes, last use, 7-day call count and 5 latest calls |
| `GET /v1/w/{wid}/ai-connections/{id}/activity` | the same visibility; the 50 latest calls from `mcp_tool_calls` |
| `DELETE /v1/w/{wid}/ai-connections/{id}` | your own, or anyone's with the integrations permission; 204; audited |
| `POST /v1/w/{wid}/ai-connections/revoke-all` | owners and admins ("Disconnect all"); audited |
| `GET/PUT /v1/w/{wid}/ai-connections/settings` | phase A's mode, now shown on the page |

### The flow

1. The client finds `/mcp`'s 401, the protected resource metadata, then our metadata.
2. **Registration.** A URL `client_id` is a Client ID Metadata Document: fetched through `security/ssrf.py` (https only, public addresses only, the checked address dialled, no redirects, 5 s, 5 KB), its `client_id` must equal the URL, it must have `client_name` and `redirect_uris`, and use `none`. Kept a day; a failed re-read keeps a copy up to a week old. Otherwise the client registered with DCR.
3. **Authorize.** `response_type=code`, PKCE S256 (a 43-character challenge), `redirect_uri` exactly as registered (a loopback one on any port), `resource` equal to `/mcp` when given (when left out it means `/mcp`). The request waits 10 minutes in Valkey and the browser goes to `dashboard…/connect/authorize?request=…`.
4. **Consent.** Clerk signs the member in if needed and brings them back. They pick one workspace (all roles may connect; a workspace whose AI connections are off is shown but can't be picked), untick groups they don't want, and Allow or Cancel. A request is decided once.
5. **Code.** 60 seconds, single use, hashed, bound to the client, redirect URI, PKCE challenge, resource, member, workspace and scopes.
6. **Tokens.** The exchange makes the connection (`mcp_connections`) and a token family.

### The token model

| | Shape | Lifetime | Stored |
|---|---|---|---|
| Authorization code | `shc_` + 43 | 60 s, single use. A second use revokes the connection the first made | SHA-256 |
| Access token | `sho_` + 43 | 1 hour | SHA-256 |
| Refresh token | `shr_` + 43 | rotated on every use; a rotated one coming back revokes the connection | SHA-256 |
| Connection (grant) | — | ends after 30 days unused or 180 days after consent | row |

On `/mcp`, `OAuthResolver` (`mcp/auth.RESOLVERS`, prefix `sho_`) turns a token into an `McpPrincipal` with `credential=OAUTH` and `credential_id` = the connection id. It refuses (401 `invalid_token`) a token that is unknown, expired or revoked, whose connection is revoked, expired or idle, whose audience isn't this server's `/mcp`, whose member left, whose workspace isn't active, or whose client is blocked. The role is read on every request. `last_used_at` is written at most once a minute.

**Scopes.** The MCP tools' scopes (`workspace:read` always, plus the phase A catalogue). `messages:send` isn't offered. `offline_access`, `openid`, `email`, `profile` and unknown scopes are dropped, not refused. No `scope` asks for the protected resource metadata's default set.

**Step-up.** A tool call whose scope the connection lacks:
- most clients: HTTP 403 with `WWW-Authenticate: Bearer error="insufficient_scope", scope="<granted + missing>", resource_metadata="…"` (the MCP spec), before the transport;
- ChatGPT (a client whose redirect URIs are on chatgpt.com or openai.com): a tool error with `_meta["mcp/www_authenticate"]`, which its linking UI reads;
- API keys: unchanged, a tool error ("make a new key").

### Which registration each client uses (design §3.1, sources read 2026-10-31)

- **claude.ai, Desktop, mobile:** CIMD or DCR; callback `https://claude.ai/api/mcp/auth_callback`.
- **Claude Code:** its own CIMD with a loopback redirect on any port, or a `shk_` header.
- **ChatGPT:** CIMD preferred, DCR as the fallback; it sends `resource` and wants `iss` (both done), and uses `https://chatgpt.com/connector_platform_oauth_redirect` because we send `iss`.
- **Codex:** `codex mcp login` (OAuth; DCR in the builds we read about) or `bearer_token_env_var`.
- **MCP Inspector:** DCR.

### Pages

| Page | Path | File |
|---|---|---|
| Consent | `dashboard.amplychat.com/connect/authorize?request=…` | `apps/web/src/app/(clerk)/(app)/connect/authorize/page.tsx`, `components/ai-connections/ConsentPage.tsx` |
| Settings › Connected AI apps | `/w/{slug}/settings/ai-apps` | `…/settings/ai-apps/page.tsx`, `components/ai-connections/AiConnectionsPage.tsx` |
| Setup guide | `amplychat.com/developers/mcp` | `app/(marketing)/developers/mcp/page.tsx`, `components/marketing/developers/ConnectAiView.tsx`, `lib/marketing/connect-ai.ts`; CSS in the `C-165 connect` block at the end of `components/site/site.css` |

`/connect` joined the app's paths (`lib/hosts.ts`, `proxy.ts`), so it's served on the dashboard host and signed in.

### Code

```
apps/api/src/socialhood/
  oauth/        tokens.py (shapes, lifetimes), scopes.py (catalogue, consent words), clients.py
                (CIMD, DCR, redirect URIs), service.py (authorize, consent, token, refresh,
                revoke, metadata), routes.py (the HTTP endpoints)
  auth/mcp_oauth.py         code and token lookups by hash (cross-workspace), the access-token principal
  api/v1/connect.py         the consent page's routes
  api/v1/ai_connections.py  + the connections list, activity, revoke, revoke all
  services/ai_connections.py
  models/oauth.py           OAuthClient, McpConnection, OAuthCode, OAuthToken
  mcp/                      auth.py (OAuthResolver), http.py (403 step-up), calls.py (_meta step-up)
migrations/versions/0055_mcp_oauth.py
```

## Test it locally

1. Start the API on its own port (the phase C convention is 8149), no `--reload`, on Windows with `--loop asyncio:SelectorEventLoop`:
   ```bash
   API_BASE_URL=http://localhost:8149 WEB_BASE_URL=http://localhost:3194 \
     uv run uvicorn socialhood.main:app --port 8149 --loop asyncio:SelectorEventLoop
   ```
   and the web app on 3194 with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8149` and `NEXT_PUBLIC_APP_URL` unset (one origin).
2. Tests: `uv run pytest tests/unit/test_oauth_rules.py tests/integration/test_mcp_oauth.py` (plus phase A's files). They run the whole flow in-process, consenting as the Clerk test user.

### With the MCP Inspector

1. `npx @modelcontextprotocol/inspector` (it opens on `http://localhost:6274`).
2. The Inspector runs OAuth from the browser, so the API must allow its origin: add `http://localhost:6274` to `CORS_ALLOWED_ORIGINS` for the local run (never in production).
3. Transport **Streamable HTTP**, URL `http://localhost:8149/mcp`, then **Open Auth Settings** › **Quick OAuth Flow** (or the guided flow to see each step: metadata, DCR, authorize, token).
4. The browser goes to the consent page on `localhost:3194`: sign in, pick a workspace, Allow. Back in the Inspector, **Connect**, then **List Tools** and run `get_workspace`.
5. Settings › Connected AI apps now lists "MCP Inspector" (its DCR name) with the calls. Disconnect, and the next Inspector request gets 401.

With an API key instead: header `Authorization: Bearer shk_…`, no OAuth (phase A).

## For the owner

### Before launch

- **Environment:** production already has `API_BASE_URL=https://api.amplychat.com` and `WEB_BASE_URL=https://dashboard.amplychat.com`; the issuer, the resource and the consent page's address come from them. No new variables.
- **Clerk:** no dashboard change. The consent page is on the dashboard host, which Clerk already serves; a signed-out visitor goes to sign-in and comes back to the same `/connect/authorize?request=…` (same origin, `CLERK_AUTHORIZED_PARTIES` unchanged). Check it once on staging with a signed-out browser.
- **Privacy policy:** both directories need a section on AI connections (what we receive from AI apps, what we send them, retention: the 90-day tool-call log, how to disconnect). It isn't written in this phase.
- **Staging:** claude.ai and ChatGPT must reach the develop deployment over public HTTPS to test the real clients (design §8.6).

### Anthropic Connectors Directory (D6)

Submit at `claude.ai/directory/manage` (any paid Claude plan). What the form asks for (design §7.1, read 2026-10-31):

- server URL `https://api.amplychat.com/mcp` (remote, HTTPS; the domain matches the service);
- auth: OAuth (we offer CIMD and DCR; Anthropic-held client credentials are optional);
- name "Amplychat", a one-liner, a description up to 2,000 characters, categories;
- docs URL `https://amplychat.com/developers/mcp`, privacy policy URL `https://amplychat.com/privacy` (after the AI connections section), support `support@amplychat.com`;
- an icon (the logo mark, square PNG);
- a **test account**: a demo workspace with connected test Instagram accounts, sample posts, inbox conversations and comments, a reviewer login without 2FA that blocks them;
- the seven compliance acknowledgements (prompt injection, conversation data, AI media generation, financial transactions, …). Every tool already has a title and explicit hints, read and write are separate tools, and no tool generates media.

Listed as "Community" after an automated scan.

### OpenAI (ChatGPT apps directory, D6)

- Verify the company (unchartd) in the OpenAI Platform dashboard, with support contact details.
- Submit the app: the server URL, OAuth, a logo, screenshots, the docs URL.
- Privacy policy naming categories, purposes, recipients, retention and controls.
- A demo account with sample data and no 2FA a reviewer can't pass.
- Every tool has explicit `readOnlyHint`, `destructiveHint` and `openWorldHint` (phase A's catalogue test).
- No upgrade or checkout flow in the app: our plan errors link the informational pricing page only.
- Until it's approved, ChatGPT users connect through developer mode (Business, Enterprise and Edu, admin-enabled). The setup guide says so.
