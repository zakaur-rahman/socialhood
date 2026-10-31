/**
 * /developers/mcp (C-165 phase C): "Connect Amplychat to Claude, ChatGPT and Codex", the public
 * setup guide for the MCP server. Every claim here is about what's built for R1
 * (docs/architecture/mcp/01-design.md §1, §4.1, §7.4): Instagram publishing, inbox and comments
 * read, drafts only for replies. Not to claim: TikTok, sending DMs from the AI, "official" or
 * "verified" partner wording, AI that posts on its own, virus-scanned uploads. ChatGPT is
 * qualified (developer mode on Business, Enterprise and Edu) until the OpenAI listing is approved.
 *
 * It sits beside /developers/api: the footer's Developers column and llms.txt's Developers
 * section list both.
 */

import { SITE_NAME } from "./site";

export const CONNECT_AI_PATH = "/developers/mcp";
export const CONNECT_AI_UPDATED = "2026-11-01";

/** The MCP server's address, from the same variable the API reference uses. */
export function mcpUrl(apiBase: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL): string {
  return `${(apiBase || "https://api.amplychat.com").replace(/\/+$/, "")}/mcp`;
}

export const CONNECT_AI_META = {
  title: "Connect Amplychat to Claude, ChatGPT and Codex",
  description:
    "Schedule Instagram posts and read your inbox, comments and analytics from Claude, ChatGPT or Codex: setup for the Amplychat MCP server, plans and safety.",
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
      who: "Sign in with your Amplychat account, or use an API key (Pro and Max).",
      steps: [
        { text: "Add the server:", code: `claude mcp add --transport http amplychat ${url}` },
        { text: "In Claude Code, run /mcp, pick amplychat and authenticate. Your browser opens Amplychat to choose the workspace and allow it." },
        {
          text: "Or, with an API key from Settings › Integrations (pick the AI app scopes you want):",
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
      who: "Use an API key (Pro and Max), or sign in with OAuth.",
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
    body: "Single photos and videos, carousels, Reels and Stories, with the caption, first comment, collaborators and time, or the next free slot. The same checklist as the composer runs first.",
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
    body: "Search what your knowledge base says, add a note or a question and answer, and see automations and pause or resume them.",
  },
  {
    title: "Ask Amplychat",
    body: "Ask Amplychat's own assistant, which answers with cited numbers. It uses your plan's AI credits, as in the app.",
    ai: true,
  },
];

export type PlanRow = { label: string; free: string; pro: string; max: string };

export const PLAN_ROWS: readonly PlanRow[] = [
  { label: "Connect Claude, ChatGPT or Codex (sign in)", free: "Yes", pro: "Yes", max: "Yes" },
  { label: "Read inbox, comments, analytics, posts", free: "Yes", pro: "Yes", max: "Yes" },
  { label: "Save draft posts and reply drafts", free: "Yes", pro: "Yes", max: "Yes" },
  { label: "Schedule, change and cancel posts", free: "No", pro: "Yes", max: "Yes" },
  { label: "Add knowledge, pause and resume automations", free: "No", pro: "Yes", max: "Yes" },
  { label: "Connect with an API key", free: "No", pro: "Yes", max: "Yes" },
  { label: "Tool calls a day", free: "100", pro: "2,000", max: "10,000" },
  { label: "Posts scheduled from AI apps a day", free: "None", pro: "25", max: "100" },
  { label: "Files uploaded from AI apps a day", free: "20 (500 MB)", pro: "200 (10,000 MB)", max: "1,000 (50,000 MB)" },
];

export const SAFETY: readonly Capability[] = [
  {
    title: "Nothing is sent from your inbox without you",
    body: "AI apps can read conversations and prepare replies. Sending a message or a comment reply stays in Amplychat, with a person.",
  },
  {
    title: "Posts wait at least 5 minutes",
    body: "A post scheduled by an AI app is at least 5 minutes out, so your team can see it in the calendar and cancel it.",
  },
  {
    title: "It acts as you, never more",
    body: "A connection is one member in one workspace. It can only do what that member's role allows, and only what they allowed when they connected.",
  },
  {
    title: "Your switch, your list",
    body: "Owners and admins choose what AI apps may do: off, read only, read and drafts, or everything. Settings › Connected AI apps lists every connection with its recent activity, and Disconnect works at once.",
  },
  {
    title: "Every action is recorded",
    body: "Each tool call is logged with the member, the app, the tool and the outcome, and kept 90 days. We don't store your conversation with the AI.",
  },
  {
    title: "Customer messages are labelled",
    body: "Messages and comments written by your customers come back marked as third-party content, so the AI treats them as data rather than instructions.",
  },
];

export const CONNECT_AI_FAQ = [
  {
    question: "Which plan do I need to connect Claude or ChatGPT?",
    answer: `Any plan, Free included. On Free, AI apps can read your inbox, comments, analytics and posts and save drafts; scheduling posts, adding knowledge and pausing automations from an AI app are part of Pro and Max. API keys are Pro and Max.`,
  },
  {
    question: "Can the AI reply to my customers' DMs?",
    answer: `No. It can read conversations and prepare a reply, and you send it from ${SITE_NAME}. Sending from an AI app isn't available.`,
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
