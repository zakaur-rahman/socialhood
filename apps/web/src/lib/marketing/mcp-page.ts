/**
 * /mcp (C-165): the product page for Amplychat's MCP server, for business owners and creators.
 * The setup steps live on /developers/mcp (connect-ai.ts) and the key steps on
 * /developers/mcp/api-key (mcp-api-key.ts); this page says what it is, where it works, what to ask
 * and what it costs, and links to both. Plans and safety are imported from connect-ai.ts, never
 * copied. Every prompt below uses a tool that exists (docs/architecture/mcp/03-phase-a.md and
 * 04-phase-b.md). Not to claim: TikTok, sending DMs from the AI, "official" or "verified" partner
 * wording, a listing in ChatGPT's apps (not yet), or that Cursor, VS Code and the like are tested.
 */

import { SITE_NAME } from "./site";

export const MCP_PAGE_PATH = "/mcp";
export const MCP_PAGE_UPDATED = "2026-11-11";
export const MCP_SETUP_PATH = "/developers/mcp";
export const MCP_API_KEY_PATH = "/developers/mcp/api-key";

export const MCP_PAGE_H1 = "Instagram MCP server for Claude and ChatGPT";

export const MCP_PAGE_META = {
  title: `${MCP_PAGE_H1} · ${SITE_NAME}`,
  description:
    "Ask Claude, ChatGPT or Codex to schedule Instagram posts, sum up your DMs and read analytics. See where it works, what to ask, plans and safety.",
};

export type WhereCard = { id: string; title: string; body: string; note?: string };

/** Where it can be used. Who-can-use facts match connect-ai.ts `clientGuides`. */
export const WHERE_CARDS: readonly WhereCard[] = [
  {
    id: "claude",
    title: "Claude (claude.ai, desktop and mobile)",
    body: "Add Amplychat as a custom connector. Any Claude plan can add one (the Free plan, one). On Team and Enterprise an Owner adds it.",
    note: "You sign in to Amplychat and pick the workspace.",
  },
  {
    id: "claude-code",
    title: "Claude Code",
    body: "Add the server with one command and sign in, or use an API key (Business and Agency). It can also upload a video you edited and schedule it as a Reel.",
  },
  {
    id: "chatgpt",
    title: "ChatGPT",
    body: "For now through developer mode, which is in beta for ChatGPT Business, Enterprise and Edu and turned on by an admin. A listing in ChatGPT's apps comes later.",
  },
  {
    id: "codex",
    title: "Codex",
    body: "Use an API key (Business and Agency), or sign in with OAuth. Like Claude Code, it can upload an edited video and schedule it.",
  },
  {
    id: "other",
    title: "Other MCP apps",
    body: "It should work with any app that supports remote MCP servers over Streamable HTTP, with OAuth sign-in or a bearer header, for example Cursor or VS Code.",
    note: "These use the same address, but we haven't tested them yet.",
  },
];

/** C-169: the server can require the preview; it can't prove a person read it. */
export const ALWAYS_ALLOW_LINE = "If you set your AI app to always allow Amplychat's tools, it can give the yes itself, so keep approvals on for changes.";

export type Ask = { prompt: string; result: string; plan?: string };

export const ASKS: readonly Ask[] = [
  {
    prompt: "Schedule this Reel for Friday at 6 pm.",
    result:
      "The AI shows a preview with the time, the account and the composer's checklist. Nothing is scheduled until you say yes, and your team is told. Ask it to post now and it publishes right after your yes.",
    plan: "Creator and Business",
  },
  {
    prompt: "Sum up this week's DMs.",
    result: "It reads your recent conversations and tells you what people asked, in one short list.",
  },
  {
    prompt: "What are people saying under my last post?",
    result: "It reads the comments and gives you the topics and the mood, with the numbers Amplychat calculates.",
  },
  {
    prompt: "Which posts did best this month?",
    result: "It reads your post analytics and ranks the posts by how they performed.",
  },
  {
    prompt: "Draft a reply to the latest pricing question.",
    result: `It writes the reply and saves it as a suggestion in the conversation. It is a draft only: you read it and send it from ${SITE_NAME}.`,
  },
  {
    prompt: "Add our new return policy to the knowledge base.",
    result: "It drafts a note and it waits on your Knowledge page. You read it and approve it, and then your AI replies can use it. Your plan's knowledge limit applies.",
    plan: "Creator and Business",
  },
  {
    prompt: "When someone comments \"price\" on my last post, DM them the price.",
    result:
      "It finds your latest post and shows a preview: the post, the keyword, the DM, and any live automation with the same keyword. Nothing is created until you say yes, and it's saved off. Turn it on in Amplychat, or ask the AI to: it shows a preview and waits for your yes again. Then the automation sends the DMs. Your team is told, and you can ask the AI to pause it.",
    plan: "Creator and Business",
  },
  {
    prompt: "Edit this video and post it.",
    result:
      "In Claude Code or Codex, it trims the video with your own tools, uploads it to your media library and schedules it as a Reel, after you approve the preview.",
    plan: "Creator and Business",
  },
];

export const HOW_STEPS: readonly { title: string; body: string }[] = [
  {
    title: "Add the server address",
    body: "Paste Amplychat's address into your AI app as a custom connector or MCP server. Each app's steps are in the setup guide.",
  },
  {
    title: "Sign in and pick the workspace",
    body: "Amplychat opens. Sign in, choose the workspace, check what the app may do and choose Allow.",
  },
  {
    title: "Ask in plain words",
    body: "Turn the connector on in a chat and ask. The AI picks the right tool and shows you what it did.",
  },
];

export const CONFIRM_LINE =
  "Before a post is scheduled or published, a scheduled post is changed or cancelled, or an automation is created, changed, paused or turned on, Amplychat requires a preview, and the AI shows it to you and waits for your yes. Editing a draft post is saved at once. New knowledge also waits for you to approve it in Amplychat.";

export const MCP_PAGE_FAQ = [
  {
    question: "What is MCP?",
    answer: `MCP (Model Context Protocol) is an open standard that lets an AI app use tools from another service. ${SITE_NAME} runs an MCP server, so Claude, ChatGPT or Codex can work with your workspace the way you would in the app.`,
  },
  {
    question: "Do I need to be a developer?",
    answer:
      "No. In Claude on the web, desktop or mobile, you paste one address and sign in. The setup guide lists the clicks for each app.",
  },
  {
    question: "Does the AI post to my accounts by itself?",
    answer:
      "No. It only acts when you ask, and Amplychat requires a preview before a post is scheduled or published, or a scheduled post is changed or cancelled. Owners and admins are told each time. " + ALWAYS_ALLOW_LINE,
  },
  {
    question: "Can the AI message my customers?",
    answer: `Not by itself. It can read conversations and draft replies that you send from ${SITE_NAME}. On Creator and Business it can also set up a keyword automation. It is saved off. You turn it on in ${SITE_NAME}, or the AI app does after a preview and your yes, and then the automation sends the DMs, as one made in the app does. You can pause it at any time, and your team is told.`,
  },
  {
    question: "Does this cost extra?",
    answer: `There is no separate fee. It's part of your ${SITE_NAME} plan: every plan can connect and read, Creator and Business can schedule and publish posts, draft knowledge for you to approve, and create automations and turn them on and off, and each plan has a daily limit on tool calls. Your AI app's own plan is billed by that app.`,
  },
  {
    question: "Can I use it with Cursor or VS Code?",
    answer:
      "It should work with any app that supports remote MCP servers over Streamable HTTP, using OAuth sign-in or a bearer header. We haven't tested those apps yet, so treat them as untested.",
  },
] as const;
