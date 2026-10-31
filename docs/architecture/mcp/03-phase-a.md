# 03 · MCP server: phase A (core, API keys, read tools)

- **Status:** built on `feature/mcp-core`, 2026-10-31. Conflicts and small calls: C-165 (phase A) in `docs/CONFLICTS.md`.
- **Design:** [01-design.md](01-design.md), decisions [02-decisions.md](02-decisions.md).
- **Next:** phase B (writes and media uploads), phase C (OAuth, the connect page, Settings › Connected AI apps).

## What was built

**The server.** `https://api.amplychat.com/mcp`, inside the API (D7):

- the official `mcp` SDK, 2.3 (`apps/api/pyproject.toml`), its low-level `Server` with our own `tools/list` and `tools/call` handlers;
- Streamable HTTP, **stateless** (`stateless_http`), JSON responses. No `Mcp-Session-Id` is issued, so any uvicorn worker serves any request;
- both protocol eras: the `initialize` handshake up to 2025-11-25, and the 2026-07-28 `server/discover` revision;
- DNS-rebinding protection: the `Host` must be `API_BASE_URL`'s host (or `MCP_ALLOWED_HOSTS`, or localhost outside production), and a browser `Origin` must be one of `CORS_ALLOWED_ORIGINS`;
- `MCP_ENABLED=false` turns `/mcp` off for the whole server (404).

**Sign-in: API keys.** `Authorization: Bearer shk_…`, the public API's keys (GR-25):

- the key acts as **the member who made it, with their current role**. A key whose maker left the workspace stops working;
- `workspace:read` is always granted. The other scopes come from the key. Ten MCP scopes joined the key catalogue (`posts:read`, `posts:write`, `media:write`, `replies:draft`, `comments:read`, `analytics:read`, `knowledge:read`, `knowledge:write`, `automations:write`, `ask`). `conversations:read` and `automations:read` already existed;
- no token: `401` with `WWW-Authenticate: Bearer resource_metadata="…/.well-known/oauth-protected-resource/mcp"`. A bad, revoked or orphaned key: the same with `error="invalid_token"` and the reason. Unknown keys also count against the caller's IP (60 a minute), as on the public API;
- the protected resource metadata (RFC 9728) is served at `/.well-known/oauth-protected-resource/mcp` and `/.well-known/oauth-protected-resource`. Its authorization server, the API's own origin, answers from phase C.

**Every call goes through one path** (`mcp/calls.py`): the workspace's mode, the scope, the role, the plan, the rate limits (`mcp` 120 a minute per key, `mcp_workspace` 300 a minute per workspace), the daily cap (`mcp_calls_daily`: Free 100, Pro 2,000, Max 10,000), the arguments, idempotency for writes, the tool, then the audit. Refusals are tool errors (`isError`) in the app's own words, never HTTP errors.

**The kill switch.** `workspaces.ai_connections_mode`: `off`, `read_only`, `read_drafts` or `full` (default). The plan caps it (`ai_connections`, D2): Free goes up to `read_drafts`. Owners and admins set it with `GET/PUT /v1/w/{wid}/ai-connections/settings`. When it's `off`, only `get_workspace` is listed, and it says why.

**The audit.** `mcp_tool_calls`: one row per call, whatever the outcome. It records the member, the key, the client (`clientInfo`, else the User-Agent), the tool, a digest plus a redacted copy of the arguments, the outcome, the error code and the latency. It never stores results or customer text.

**Thirteen read tools.** Each needs one scope, has explicit `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint`, and returns `structuredContent` that matches its `outputSchema`:

| Tool | Scope | Role | Backing |
|---|---|---|---|
| `get_workspace` | `workspace:read` | any | workspace, plan, mode, today's calls |
| `list_accounts` | `workspace:read` | any | `social_accounts`, the calendar's accounts rail |
| `list_scheduled_posts` | `posts:read` | admin | Ask's `list_scheduled_posts` |
| `get_scheduled_post` | `posts:read` | admin | `scheduled_posts.posts.get` (with the checklist) |
| `get_best_times` | `posts:read` | admin | `best_times.best_times`, `slots.next_free` |
| `list_media` | `posts:read` | admin | `library.list_library` |
| `get_media_upload` | `media:write` | admin | `mcp_uploads` (tickets come in phase B) |
| `list_conversations` | `conversations:read` | any | Ask's `search_conversations` |
| `get_conversation` | `conversations:read` | any | Ask's `get_conversation` |
| `get_post_comments_summary` | `comments:read` | any | Ask's `sentiment_distribution`, `comment_topics`, `get_post_comments` |
| `get_analytics_summary` | `analytics:read` | any | Ask's `compare_periods`, `post_performance`, `top_posts` |
| `search_knowledge` | `knowledge:read` | admin | Ask's `search_knowledge` |
| `list_automations` | `automations:read` | admin | Ask's `list_automations` |

All 13 are read tools, so every plan can use them, Free included. Customer-written text (names, messages, comments, topics, crawled excerpts) is returned only in fields ending in `_text`. When a result carries any, the text copy says once, before the JSON, that those fields are third-party content. Times come back in the workspace's zone with UTC ("Fri 6 Nov 2026, 6:00 pm Asia/Kolkata (12:30 UTC)").

### Code

```
apps/api/src/socialhood/
  mcp/
    server.py       the SDK server, install() at /mcp, INSTRUCTIONS
    http.py         auth in front of the transport; 401s; protected resource metadata
    auth.py         CredentialResolver, ApiKeyResolver, resolve_bearer
    principal.py    McpPrincipal, McpRequest (context variable)
    registry.py     McpTool, McpRegistry, Access, ToolInput/ToolOutput, WriteInput/WriteOutput
    calls.py        the gate, limits, daily cap, idempotency, audit; list_tools, call_tool
    context.py      ToolCall (what a handler gets) and agent_context()
    idempotency.py  WriteGuard (idempotency_key and the dedupe window)
    audit.py        the mcp_tool_calls row and argument redaction
    results.py      success/failure results, the _text label
    tools/          workspace, posts, media, inbox, insights, knowledge
  auth/mcp_credentials.py   an shk_ key → McpPrincipal (the cross-workspace lookup lives in auth/)
  api/v1/ai_connections.py  the mode setting
  models/mcp.py             McpToolCall, McpUpload, AiConnectionsMode
migrations/versions/0054_mcp_server.py
```

## Run it locally

1. Start the API as usual (`uv run uvicorn socialhood.main:app --port 8000`, no `--reload`). `/mcp` is on by default.
2. In the app, make an API key in Settings › API keys with the scopes you want. The workspace must be on Pro or Max to make a key (PD-6).
3. Check it:

   ```bash
   curl -s http://localhost:8000/mcp -H "Authorization: Bearer shk_…" \
     -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
     -H "MCP-Protocol-Version: 2025-11-25" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
   ```

   The MCP Inspector works too: `npx @modelcontextprotocol/inspector`, Streamable HTTP, URL `http://localhost:8000/mcp`, and an `Authorization` header.

Tests: `uv run pytest tests/unit/test_mcp_registry.py tests/integration/test_mcp_server.py tests/integration/test_mcp_tools.py tests/integration/test_mcp_calls.py`. They use the SDK's own client against the mounted app in-process, so they need no port.

## Connect a client

**Claude Code** (checked against code.claude.com/docs/en/mcp, 2026-10-31):

```bash
claude mcp add --transport http amplychat https://api.amplychat.com/mcp \
  --header "Authorization: Bearer shk_…"
```

- Add `--scope user` to use it in every project. The default, `local`, covers this project only.
- `/mcp` in Claude Code shows whether it connected. `claude mcp add` doesn't check the key.
- With an `Authorization` header, Claude Code doesn't try OAuth for this server. Remove the header to use OAuth once phase C ships it.

**Codex CLI** (checked against learn.chatgpt.com/docs/extend/mcp, 2026-10-31). In `~/.codex/config.toml`, or a trusted project's `.codex/config.toml`:

```toml
[mcp_servers.amplychat]
url = "https://api.amplychat.com/mcp"
bearer_token_env_var = "AMPLYCHAT_API_KEY"   # the variable's name, not the key
default_tools_approval_mode = "writes"        # read-only tools run without asking
```

Then `export AMPLYCHAT_API_KEY=shk_…` and start Codex. `tool_timeout_sec` defaults to 60, and every phase A tool answers well within it. Codex's docs show no CLI flag for a bearer token (`codex mcp add … --url` documents OAuth only), so use the config file.

**claude.ai and ChatGPT** need OAuth. That's phase C.

## For phase B (writes and media)

- **Write tools:**
  - The input model extends `WriteInput`, which carries `idempotency_key`. The output model extends `WriteOutput`, which carries `duplicate_of_previous_call`. The registry refuses a write that doesn't.
  - Register with `access=Access.WRITE`, or `Access.DRAFT` for a draft-only path. Set `destructive=True` for overwrites and cancels, and `open_world=True` when the effect leaves the workspace.
  - Set `dedupe_window_s=600` where an identical resend must not run twice (`create_post`).
- **The pipeline commits.** It commits the session after a write's handler returns, and rolls back on any error. A handler never commits.
- **Free's draft-only posting:**
  - `MODE_ADMITS` and the plan cap already refuse `Access.WRITE` on Free with `entitlement_required`.
  - `create_post` with `when: "draft"` is the one argument-dependent case. Either register a separate draft-tier tool, or have the handler raise `entitlement_error("ai_connections")` when `when` isn't `"draft"` and `call.mode` isn't `full`.
- **Uploads:** `mcp_uploads` exists, and `get_media_upload` reads it. `start_media_upload` and `finish_media_upload` write it.
- **Audit:** the R2 hook into GR-19's `audit_events` for writes is not done. Add it in `calls._run` after the commit.

## For phase C (OAuth)

- Add an `OAuthResolver` with `prefix = "sho_"` to `mcp/auth.RESOLVERS`:
  - its `resolve(token, env)` returns an `McpPrincipal` with `credential=CredentialKind.OAUTH` and `credential_id` = the connection id;
  - a dead token raises `CredentialRefused(reason)`.

  Tools, the gate and the audit don't change. The audit row then fills `connection_id` instead of `api_key_id`.
- Serve `/.well-known/oauth-authorization-server` at the API's origin, the issuer the protected resource metadata already names.
- Step-up for a missing scope is a tool error today (`forbidden`, naming the scope). OAuth clients want `403 insufficient_scope` with `scope="…"`, and ChatGPT wants `_meta["mcp/www_authenticate"]`. Add both in `calls._gate` for OAuth principals.
- Settings › Connected AI apps reads `GET /v1/w/{wid}/ai-connections/settings` (mode) and `mcp_tool_calls` (activity), and needs the connections list.
