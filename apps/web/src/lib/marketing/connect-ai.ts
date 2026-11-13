/**
 * /developers/mcp (C-165 phase C): "Set up the Amplychat MCP server in Claude, ChatGPT, Codex", the public
 * setup guide for the MCP server. Every claim here is about what's built for R1
 * (docs/architecture/mcp/01-design.md §1, §4.1, §7.4): Instagram publishing, inbox and comments
 * read, drafts only for replies. Not to claim: TikTok, sending DMs from the AI, "official" or
 * "verified" partner wording, AI that posts on its own, virus-scanned uploads. ChatGPT is
 * qualified (developer mode on Business, Enterprise and Edu) until the OpenAI listing is approved.
 *
 * It sits beside /developers/api: the footer's Developers column and llms.txt's Developers
 * section list both.
 */

import reference from "./mcp-tools.json";
import { SITE_NAME } from "./site";

export const CONNECT_AI_PATH = "/developers/mcp";
export const CONNECT_AI_UPDATED = "2026-11-11";

/** The MCP server's address, from the same variable the API reference uses. */
export function mcpUrl(apiBase: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL): string {
  return `${(apiBase || "https://api.amplychat.com").replace(/\/+$/, "")}/mcp`;
}

export const CONNECT_AI_META = {
  title: "Set up the Amplychat MCP server in Claude, ChatGPT, Codex",
  description:
    "How to add the Amplychat MCP server to Claude, Claude Code, ChatGPT or Codex: the server address, sign-in or an API key, plans and safety.",
};

export type Step = { text: string; code?: string };
export type ClientGuide = {
  id: string;
  name: string;
  /** Who can use it, in one line. */
  who: string;
  steps: readonly Step[];
  note?: string;
};

export function clientGuides(url: string = mcpUrl()): readonly ClientGuide[] {
  return [
    {
      id: "claude",
      name: "Claude (claude.ai, desktop and mobile)",
      who: "Any Claude plan can add a custom connector (the Free plan, one). On Team and Enterprise an Owner adds it.",
      steps: [
        { text: "In Claude, open Settings, then Connectors, and choose Add custom connector." },
        { text: "Name it Amplychat and paste the server address:", code: url },
        { text: "Choose Connect. Amplychat opens: sign in, pick the workspace, check what Claude may do and choose Allow." },
        { text: "Back in Claude, turn the connector on in a chat and ask, for example, “What did people ask in my DMs this week?”" },
      ],
    },
    {
      id: "claude-code",
      name: "Claude Code",
      who: "Sign in with your Amplychat account, or use an API key (Business and Agency).",
      steps: [
        { text: "Add the server:", code: `claude mcp add --transport http amplychat ${url}` },
        { text: "In Claude Code, run /mcp, pick amplychat and authenticate. Your browser opens Amplychat to choose the workspace and allow it." },
        {
          text: "Or, with an API key from Settings › API keys (pick the AI app scopes you want):",
          code: `claude mcp add --transport http amplychat ${url} \\\n  --header "Authorization: Bearer $AMPLYCHAT_API_KEY"`,
        },
      ],
      note: "Add --scope user to use it in every project. With a key in the header, Claude Code doesn't ask you to sign in.",
    },
    {
      id: "chatgpt",
      name: "ChatGPT",
      who: "Until Amplychat is listed in ChatGPT's apps, connecting needs developer mode, which is in beta for ChatGPT Business, Enterprise and Edu, turned on by an admin.",
      steps: [
        { text: "In ChatGPT's settings, under Apps and Connectors, turn on developer mode (or ask your workspace admin)." },
        { text: "Create an app with this server address and OAuth sign-in:", code: url },
        { text: "Sign in to Amplychat when ChatGPT asks, pick the workspace and choose Allow." },
      ],
      note: "ChatGPT confirms every action that changes something before it runs.",
    },
    {
      id: "codex",
      name: "Codex",
      who: "Use an API key (Business and Agency), or sign in with OAuth.",
      steps: [
        {
          text: "Add this to ~/.codex/config.toml (or a trusted project's .codex/config.toml):",
          code: `[mcp_servers.amplychat]\nurl = "${url}"\nbearer_token_env_var = "AMPLYCHAT_API_KEY"\ndefault_tools_approval_mode = "writes"`,
        },
        { text: "Set the key in your shell and start Codex:", code: "export AMPLYCHAT_API_KEY=shk_…" },
        { text: "To sign in instead of using a key, remove the bearer_token_env_var line and run:", code: "codex mcp login amplychat" },
      ],
      note: "default_tools_approval_mode = \"writes\" lets reads run without asking and keeps a confirmation for anything that changes something. If your Codex sandbox blocks the network, approve the upload command when it runs.",
    },
  ];
}

export type Capability = { title: string; body: string; ai?: boolean };

export const CAPABILITIES: readonly Capability[] = [
  {
    title: "Schedule Instagram posts",
    body: "Single photos and videos, carousels, Reels and Stories, with the caption, first comment and collaborators, for a set time, the next free slot or right now. The same checklist as the composer runs first.",
  },
  {
    title: "Edit a video, then post it",
    body: "In Claude Code or Codex, the AI can trim a video with your tools, upload it straight to your Amplychat media library and schedule it as a Reel in one conversation.",
  },
  {
    title: "Read your inbox",
    body: "Search conversations and read recent messages. The AI can prepare a reply for you to send in Amplychat; it can't send it.",
  },
  {
    title: "Comments and analytics",
    body: "What people are saying on a post, the topics and sentiment, and how posts and accounts performed, with the numbers Amplychat calculates.",
  },
  {
    title: "Knowledge and automations",
    body: "Search what your knowledge base says and see your automations. Draft a note, a question and answer, or a keyword automation, such as a DM to everyone who comments a word on your last post. Knowledge is used after you approve it in Amplychat. A new automation is saved off, and the AI can turn one on or off after it shows you a preview and you say yes.",
  },
  {
    title: "Ask Amplychat",
    body: "Ask Amplychat's own assistant, which answers with cited numbers. It can read anything you can see in Amplychat, including the inbox, and it uses your plan's AI credits, as in the app.",
    ai: true,
  },
];

export type PlanRow = { label: string; free: string; pro: string; max: string; agency: string };

/** The numbers are billing/plans.py's (plan-table.json); ConnectAiView.test.tsx checks them. */
export const PLAN_ROWS: readonly PlanRow[] = [
  { label: "Connect Claude, ChatGPT or Codex (sign in)", free: "Yes", pro: "Yes", max: "Yes", agency: "Yes" },
  { label: "Read inbox, comments, analytics, posts", free: "Yes", pro: "Yes", max: "Yes", agency: "Yes" },
  { label: "Save draft posts and reply drafts", free: "Yes", pro: "Yes", max: "Yes", agency: "Yes" },
  { label: "Schedule, publish, change and cancel posts", free: "No", pro: "Yes", max: "Yes", agency: "Yes" },
  { label: "Draft knowledge for you to approve", free: "No", pro: "Yes", max: "Yes", agency: "Yes" },
  { label: "Create automations and turn them on and off", free: "No", pro: "Yes", max: "Yes", agency: "Yes" },
  { label: "Make an API key", free: "No", pro: "No", max: "Yes", agency: "Yes" },
  { label: "Tool calls a day", free: "100", pro: "2,000", max: "2,000", agency: "10,000" },
  { label: "Posts scheduled from AI apps a day", free: "None", pro: "100", max: "100", agency: "300" },
  {
    label: "Files uploaded from AI apps a day",
    free: "20 (500 MB)",
    pro: "50 (2,500 MB)",
    max: "200 (10,000 MB)",
    agency: "1,000 (50,000 MB)",
  },
];

export type ToolRow = (typeof reference.tools)[number];

const TOOL_ORDER = ["read", "draft", "write"];

/**
 * Every tool on the server (01-design.md §7.3), reads first. mcp-tools.json is written from the
 * registry by apps/api/scripts/export_mcp_tools.py, and an API test fails when it is stale, so
 * this list can't drift from the server.
 */
export const TOOLS: readonly ToolRow[] = [...reference.tools].sort(
  (a, b) => TOOL_ORDER.indexOf(a.access) - TOOL_ORDER.indexOf(b.access),
);

/** A tool's kind in plain words, and the least mode that lets it run. */
export const TOOL_KIND: Record<string, string> = { read: "Read", draft: "Draft", write: "Change" };

export const SAFETY: readonly Capability[] = [
  {
    title: "Nothing is sent from your inbox without you",
    body: "AI apps can read conversations and prepare replies. Sending a message or a comment reply stays in Amplychat, with a person. An automation set up from an AI app is saved off and sends nothing until it is turned on. The AI app can turn it on after it shows you a preview and you say yes, and you can pause it at any time.",
  },
  {
    title: "You approve what reaches your customers",
    body: "AI apps do the drafting and you stay in control. New knowledge isn't used until you approve it in your dashboard. A new automation is saved off, an AI app turns one on or off after a preview and your yes, and it can't change one that's on until it is paused.",
  },
  {
    title: "A preview and a yes before a change",
    body: "Amplychat refuses these until the AI app has fetched a preview to show you: scheduling a post or publishing it now, changing or cancelling a scheduled post, and creating, changing, pausing or turning on an automation. A time such as the next free slot is confirmed when you say yes. Editing a draft post is saved at once. If you set your AI app to always allow Amplychat's tools, it can give the yes itself, so keep approvals on for changes.",
  },
  {
    title: "It acts as you, never more",
    body: "A connection is one member in one workspace. It can only do what that member's role allows, and only what they allowed when they connected.",
  },
  {
    title: "Your switch, your list",
    body: "Owners and admins choose what AI apps may do: off, read only, read and drafts, or everything. Settings › Connected AI apps lists every connected app, and Settings › API keys every key, each with its recent tool calls. Disconnecting an app or revoking a key works at once.",
  },
  {
    title: "Every action is recorded",
    body: "Each tool call is logged with the member, the app, the tool and the outcome, and kept 90 days. Owners and admins are told when an AI app changes a post or an automation, in Amplychat and by email; each of them can turn the emails off. We don't store your conversation with the AI.",
  },
  {
    title: "Customer messages are labelled",
    body: "Messages and comments written by your customers come back marked as third-party content, so the AI treats them as data rather than instructions.",
  },
];

export const CONNECT_AI_FAQ = [
  {
    question: "Which plan do I need to connect Claude or ChatGPT?",
    answer: `Any plan, Free included. On Free, AI apps can read your inbox, comments, analytics and posts and save drafts; scheduling and publishing posts, drafting knowledge for you to approve, and creating automations and turning them on and off from an AI app are part of Creator and Business. API keys are on Business and Agency.`,
  },
  {
    question: "Can the AI reply to my customers' DMs?",
    answer: `No. It can read conversations and prepare a reply, and you send it from ${SITE_NAME}. Sending from an AI app isn't available. It can set up a keyword automation on Creator and Business. It is saved off; once it is turned on, by you in ${SITE_NAME} or by the AI app after a preview and your yes, the automation sends the DMs, as one made in the app does.`,
  },
  {
    question: "How do I disconnect an AI app?",
    answer: `In ${SITE_NAME}, open Settings › Connected AI apps and choose Disconnect. It stops working on its next request. Owners and admins can disconnect anyone's, or all of them at once.`,
  },
  {
    question: "Can one connection use two workspaces?",
    answer: "No. Each connection is one workspace, chosen when you allow it. To use another, connect again and pick that workspace; Claude and ChatGPT let you add the same server twice under different names.",
  },
  {
    question: "Does the AI see messages from my customers?",
    answer: `Only when you ask it something that needs them, and only what your role can see. What the AI reads is sent to that AI's provider under their terms. ${SITE_NAME} logs which tools ran, never your conversation with the AI.`,
  },
  {
    question: "How do I get a video from Claude to Instagram?",
    answer: "In Claude Code or Codex, the AI uploads the file straight to your media library and schedules it. In claude.ai or ChatGPT, the AI can import a file from a public link, or give you a short link to drop the file into Amplychat.",
  },
] as const;
