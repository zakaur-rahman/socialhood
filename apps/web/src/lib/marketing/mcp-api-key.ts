/**
 * /developers/mcp/api-key (C-165): connect an AI app with an Amplychat API key instead of signing
 * in. Facts: a key needs the public_api entitlement (Pro and Max, billing/plans.py, PD-6); the key
 * acts as the member who made it with their current role (docs/architecture/mcp/03-phase-a.md);
 * the MCP scopes are schemas/api_keys.py; limits are mcp/calls.py via security/ratelimit.py.
 */

import { PLAN_ROWS, mcpUrl } from "./connect-ai";

export const API_KEY_PAGE_PATH = "/developers/mcp/api-key";
export const API_KEY_PAGE_UPDATED = "2026-11-01";

export const API_KEY_H1 = "Connect an AI app with an API key";

export const API_KEY_META = {
  title: "Connect an AI app with an Amplychat API key",
  description:
    "Use an Amplychat API key instead of signing in: config for Claude Code, Codex and other MCP apps, the scopes to pick, limits and how to keep a key safe.",
};

/** The scopes an AI app's key can carry, in plain words (schemas/api_keys.py SCOPE_DESCRIPTIONS). */
export const KEY_SCOPES: readonly { scope: string; body: string }[] = [
  { scope: "posts:read", body: "Read scheduled posts, the calendar, best times and the media library." },
  { scope: "posts:write", body: "Create, change, reschedule and cancel posts. Scheduling is Pro and Max." },
  { scope: "media:write", body: "Upload or import images and videos for posts." },
  { scope: "conversations:read", body: "Read conversations and their messages." },
  { scope: "replies:draft", body: "Prepare a reply for a member to send in Amplychat. It is never sent." },
  { scope: "comments:read", body: "Read post comments, their topics and sentiment." },
  { scope: "analytics:read", body: "Read post and account analytics." },
  { scope: "knowledge:read", body: "Search the knowledge base." },
  { scope: "knowledge:write", body: "Add a text note or a website to the knowledge base." },
  { scope: "automations:read", body: "Read automations and their runs." },
  { scope: "automations:write", body: "Pause and resume automations." },
  { scope: "ask", body: "Ask Amplychat's own assistant (uses AI credits)." },
];

export type KeyConfig = { id: string; name: string; intro: string; code: string; note?: string };

export function keyConfigs(url: string = mcpUrl()): readonly KeyConfig[] {
  return [
    {
      id: "claude-code",
      name: "Claude Code",
      intro: "Put the key in an environment variable, then add the server with a header:",
      code: `export AMPLYCHAT_API_KEY=shk_…\nclaude mcp add --transport http amplychat ${url} \\\n  --header "Authorization: Bearer $AMPLYCHAT_API_KEY"`,
      note: "Add --scope user to use it in every project. With a key in the header, Claude Code doesn't ask you to sign in.",
    },
    {
      id: "codex",
      name: "Codex",
      intro:
        "Add this to ~/.codex/config.toml (or a trusted project's .codex/config.toml), then export the key before you start Codex:",
      code: `[mcp_servers.amplychat]\nurl = "${url}"\nbearer_token_env_var = "AMPLYCHAT_API_KEY"\ndefault_tools_approval_mode = "writes"`,
      note: 'bearer_token_env_var is the variable\'s name, not the key. default_tools_approval_mode = "writes" lets reads run and keeps a confirmation for anything that changes something.',
    },
    {
      id: "other",
      name: "Other MCP apps",
      intro:
        "Apps that take a JSON config with a server address and headers usually want this shape. Names differ by app, and we haven't tested these apps.",
      code: `{\n  "mcpServers": {\n    "amplychat": {\n      "url": "${url}",\n      "headers": { "Authorization": "Bearer YOUR_API_KEY" }\n    }\n  }\n}`,
      note: "If your app can read the key from an environment variable, use that instead of pasting it.",
    },
    {
      id: "curl",
      name: "Check it with curl",
      intro: "For your own script or a quick test. This sends the MCP initialize request:",
      code: `curl -X POST ${url} \\\n  -H "Authorization: Bearer $AMPLYCHAT_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -H "Accept: application/json, text/event-stream" \\\n  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'`,
      note: "A wrong, revoked or missing key gets a 401.",
    },
  ];
}

export const WHEN_TO_USE = [
  "Headless or CI use, where nobody can sign in in a browser.",
  "Servers and scripts that call the MCP address directly.",
  "Tools without OAuth sign-in, such as Codex with a config file.",
] as const;

export const KEEP_SAFE = [
  {
    title: "Environment variables, not files",
    body: "Keep the key in an environment variable or your tool's secret store. Don't commit it or paste it into a chat.",
  },
  {
    title: "One key per tool",
    body: "Make a separate key for each app or script, named after it. If one leaks, revoke only that one.",
  },
  {
    title: "The fewest scopes",
    body: "Pick only the scopes the tool needs. You can't change a key's scopes later; make another.",
  },
  {
    title: "Revoke in Settings › API keys",
    body: "Anything using the key stops on its next request. The list shows when each key was last used.",
  },
  {
    title: "It acts as the member who made it",
    body: "A key has that member's current role, never more. If the member leaves the workspace, the key stops working.",
  },
  {
    title: "Changes are recorded",
    body: "Every tool call is logged with the key. A change a key makes, such as scheduling a post, also shows in Settings › Audit log as the member via the app's name.",
  },
] as const;

/** Rate limits (mcp/calls.py, security/ratelimit.py). */
export const KEY_LIMITS = [
  "120 requests a minute for each key, and 300 a minute for the whole workspace.",
  "Requests with an unknown key count against the caller's address (60 a minute), so a script with a wrong key is slowed.",
] as const;

/** The daily rows of the shared plans table, taken from PLAN_ROWS so the numbers never drift. */
export const KEY_PLAN_ROWS = PLAN_ROWS.filter((row) => /a day|API key/.test(row.label));

export const API_KEY_FAQ = [
  {
    question: "Which plan do I need for an API key?",
    answer: "Pro or Max. Making a key is part of the public API, which is Pro and Max. On Free, connect by signing in instead.",
  },
  {
    question: "Can I change a key's scopes?",
    answer: "No. Make a new key with the scopes you want, move the tool to it and revoke the old one.",
  },
  {
    question: "Why can't the AI app see a tool?",
    answer:
      "The tool needs a scope the key lacks, or a role the key's member doesn't have. A tool is listed only when the key's scopes open it.",
  },
] as const;
