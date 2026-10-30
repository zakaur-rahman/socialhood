/**
 * The words of /how-it-works and /features (C-160). Most lines are the site's own (the landing's
 * SETUP_STEPS, FEATURES, INTEGRATIONS and TRUST_POINTS, the feature pages in gtm-pages.ts and the FAQ);
 * the few new ones are short, plain and checked against the code named beside them. Every limit is
 * read from plan-table.json (billing/plans.py), never typed here.
 */
import {
  BellRing,
  BookOpenText,
  CalendarClock,
  ChartLine,
  Hand,
  Inbox,
  Link2,
  type LucideIcon,
  MessageCircleQuestionMark,
  MessageSquareReply,
  MessageSquareText,
  PanelsTopLeft,
  Plug,
  ScanSearch,
  ShieldCheck,
  ShoppingBag,
  Timer,
  UsersRound,
  Workflow,
} from "lucide-react";

import { FEATURES } from "@/components/marketing/landing/Features";
import { INTEGRATIONS } from "@/components/marketing/landing/Channels";
import { SETUP_STEPS } from "@/components/marketing/landing/Steps";
import { TRUST_POINTS } from "@/components/marketing/landing/Trust";
import { MODES } from "@/components/marketing/landing/data";
import {
  FAQ_24_HOURS,
  FAQ_AUTO_REPLY,
  FAQ_FOLLOW_GATE,
  FAQ_MADE_UP,
  FAQ_ACCOUNT_LOGIN,
  FAQ_TAKEOVER,
  type FaqItem,
} from "@/lib/marketing/faq";
import type { Platform } from "@/lib/api/types";
import table from "@/lib/marketing/plan-table.json";
import { SITE_NAME } from "@/lib/marketing/site";

const E = table.entitlements;
const number = new Intl.NumberFormat("en-US");
/** A plan's limit as the pricing page words it: a number, or "No limit" for null (billing/plans.py). */
export const limit = (value: number | null, unit = "") => (value === null ? "No limit" : `${number.format(value)}${unit}`);
/** A plan's allowance where 0 or false means the plan doesn't have it. */
export const has = (value: number | boolean | null, unit = "") =>
  value === false || value === 0 ? "Not included" : value === true ? "Included" : limit(value as number | null, unit);

const feature = (title: string) => {
  const found = FEATURES.find((item) => item.title === title);
  if (!found) throw new Error(`No landing feature named ${title}`);
  return found;
};
const integration = (name: string) => {
  const found = INTEGRATIONS.find((item) => item.name === name);
  if (!found) throw new Error(`No integration named ${name}`);
  return found;
};

// ---------------------------------------------------------------- /how-it-works

export type StageId = "connect" | "knowledge" | "inbox" | "reads" | "replies" | "handoff" | "automations" | "results";

export type Stage = {
  id: StageId;
  /** The tracker's short label. */
  short: string;
  title: string;
  icon: LucideIcon;
  /** One or two short paragraphs. */
  body: string[];
  /** A few specifics, each a sentence. */
  points: string[];
  /** The stage's visual spans the stage's width under the text (a wide landing scene). */
  wide?: boolean;
};

/** The journey, in order (C-160). The page renders them as an <ol> of sections, numbered by position. */
export const STAGES: Stage[] = [
  {
    id: "connect",
    short: "Connect your accounts",
    title: SETUP_STEPS[0].title,
    icon: Link2,
    // SETUP_STEPS[0], then the widget's one line of code (components/widget/WidgetSettingsPage.tsx).
    body: [SETUP_STEPS[0].body, "Add website chat by pasting one line of code into your site."],
    points: [
      // platforms/instagram/oauth.py, Embedded Signup (lib/whatsapp/embedded-signup.ts), C-077.
      "Instagram connects with Instagram's own login, for Business and Creator accounts.",
      "WhatsApp connects a number your business owns through Meta's Embedded Signup.",
      "Facebook Pages are built and connect once Meta approves them.",
    ],
  },
  {
    id: "knowledge",
    short: "Add your knowledge",
    title: SETUP_STEPS[1].title,
    icon: BookOpenText,
    body: [SETUP_STEPS[1].body],
    points: [
      // models/ai.py KnowledgeType: faq, text, url, file, site/page (GR-35); the catalogue is Pro (commerce).
      `Add text and question-and-answer pairs, links, files and your website's pages, up to ${limit(E.crawl_pages.free)} pages on Free and ${limit(E.crawl_pages.pro)} on Pro.`,
      "On Pro, the AI also answers price and stock from your product catalogue.",
      // billing/plans.py CREDIT_COSTS knowledge_test: 1.
      "Each test question uses one AI credit.",
    ],
  },
  {
    id: "inbox",
    short: "One inbox",
    title: "Every message lands in one inbox",
    icon: Inbox,
    body: [
      "Instagram DMs and comments, WhatsApp messages and website chats arrive in one list, sorted so the conversations that need a person come first.",
    ],
    points: [
      // C-082, C-083 (story replies and mentions); C-077 (Facebook).
      "Story replies and mentions arrive as conversations too.",
      "Messenger chats and Page comments join the same inbox with Meta's approval.",
      // FAQ_24_HOURS.
      "Instagram only lets a business message a customer within 24 hours of their last message, and Amplychat shows when that window closes.",
    ],
  },
  {
    id: "reads",
    short: "The AI reads and tags",
    title: "The AI reads and tags each message",
    icon: ScanSearch,
    // The Off mode's description (MODES.off): tagging happens in every mode.
    body: [
      "Every message is tagged with its intent, its sentiment and a lead score, so you can see what a customer wants and who is ready to buy. This happens in every mode, Off included.",
    ],
    points: [
      // models/ai.py Intent and Sentiment.
      "Intents include pricing, a product question, a purchase, an order's status, shipping, a complaint and a refund.",
      "Sentiment is positive, neutral or negative.",
      // billing/plans.py CREDIT_COSTS message_analysis: 1.
      "Reading a message uses one AI credit.",
    ],
  },
  {
    id: "replies",
    short: "The AI drafts or replies",
    title: "The AI drafts or replies",
    icon: MessageSquareReply,
    // gtm-pages.ts, the AI inbox's "You choose how much the AI does" and "Only your knowledge".
    body: [
      "Off, Suggest or Auto for each account. Suggest drafts a reply for you to send. Auto replies by itself when it is confident, and is part of Pro.",
      "Answers come from the documents, questions and products you add, and each draft shows the knowledge it used.",
    ],
    points: [
      MODES.suggest.description,
      // models/ai.py AiSettings (FAQ_ROBOTIC).
      "You pick the tone, the emoji level, your do's and don'ts and a sign-off.",
      // CREDIT_COSTS reply_suggestion and auto_reply: 2.
      "A draft or an automatic reply uses two AI credits.",
    ],
    wide: true,
  },
  {
    id: "handoff",
    short: "Hand-off and gaps",
    title: "Hand-off and knowledge gaps",
    icon: Hand,
    body: [
      // FAQ_MADE_UP and FAQ_TAKEOVER (services/sending.py human_takeover, models/ai.py TAKEOVER_MINUTES).
      "When the answer isn't there, the AI doesn't guess: it hands the conversation to you and records the question as a knowledge gap.",
      "When you reply yourself, in Amplychat or in the Instagram app, the AI pauses on that conversation for 2 hours by default. You can change the pause to 30 minutes, 24 hours or until you resume the AI.",
    ],
    points: [
      // gtm-pages.ts, "Escalation you can rely on" (models/ai.py EscalationReason).
      "Refunds, legal threats, complaints, abuse, low confidence, or your own phrases go to Needs you.",
      "Each unanswered question is recorded, so you know what to add to your knowledge.",
    ],
  },
  {
    id: "automations",
    short: "Automations",
    title: "Automations do the repetitive work",
    icon: Workflow,
    body: [
      "Turn comments into conversations, the way Instagram allows. Someone comments your keyword, gets a public reply if you want one, and a DM opens with a button; the link follows their tap.",
    ],
    points: [
      // models/automations.py follow_nudge (FR-AUT-22): the message is never held back.
      "A polite follow nudge can come after the link, never a condition for getting it.",
      // platforms/buckets.py (FAQ_BAN_RISK).
      "Replies are queued to stay within Instagram's sending limits, at most 750 private replies an hour for each account.",
      feature("Sequences, and broadcasts soon").body,
    ],
    wide: true,
  },
  {
    id: "results",
    short: "See what works",
    title: "See what works",
    icon: ChartLine,
    body: [feature("Analytics and the weekly report").body, feature(`Ask ${SITE_NAME}`).body],
    points: [
      feature("Comment intelligence").body,
      // agent/: proposals wait for approval (GR-36).
      `Ask ${SITE_NAME} never sends, changes or deletes anything by itself.`,
    ],
    wide: true,
  },
];

/** The questions under the flow: a subset of the site's FAQ, in its words. */
export const HOW_FAQ: FaqItem[] = [FAQ_ACCOUNT_LOGIN, FAQ_AUTO_REPLY, FAQ_MADE_UP, FAQ_TAKEOVER, FAQ_FOLLOW_GATE, FAQ_24_HOURS];

export const HOW_RELATED = [
  { label: "Every feature", href: "/features" },
  { label: "Pricing", href: "/pricing" },
  { label: "For creators", href: "/for-creators" },
  { label: "For businesses", href: "/for-businesses" },
  { label: "How sending stays safe", href: "/safety" },
  { label: "The comment-to-DM guide", href: "/guides/comment-to-dm-automations" },
] as const;

// ---------------------------------------------------------------- /features: the bento grid

export type CellSize = "xl" | "l" | "m" | "s";
export type CellStatus = "approval" | "soon" | "pro";
export type CellVisual = "inbox" | "replies" | "comments" | "publishing" | "insight" | "analytics" | "ask";

export type Cell = {
  id: string;
  title: string;
  body: string;
  icon: LucideIcon;
  size: CellSize;
  href: string;
  /** Where it isn't live, or which plan it is part of. */
  status?: CellStatus;
  /** An AI moment: the icon in iris. */
  ai?: boolean;
  visual?: CellVisual;
  /** A channel's own mark instead of the icon. */
  platform?: Platform;
};

export const CELL_STATUS_LABEL: Record<CellStatus, string> = {
  approval: "With Meta's approval",
  soon: "Coming soon",
  pro: "Pro",
};

/** The grid, in reading order (C-160). Links go to a feature's own page where it has one, else to its detail below. */
export const BENTO: Cell[] = [
  {
    id: "inbox",
    title: "One AI inbox",
    icon: Inbox,
    size: "xl",
    href: "/features/ai-inbox",
    visual: "inbox",
    body: "Instagram DMs and comments, WhatsApp and your website chat in one inbox, sorted so what needs you comes first.",
  },
  {
    id: "replies",
    title: "AI replies from your own knowledge",
    icon: MessageSquareReply,
    size: "xl",
    ai: true,
    href: "/guides/instagram-dm-auto-replies",
    visual: "replies",
    body: "Answers come from the documents, questions and products you add. When the answer isn't there it doesn't guess.",
  },
  {
    id: "comments",
    title: "Comment-to-DM automations",
    icon: Workflow,
    size: "l",
    href: "/guides/comment-to-dm-automations",
    visual: "comments",
    body: "Someone comments your keyword and gets the link in a DM, with a public reply if you want one.",
  },
  {
    id: "publishing",
    title: feature("Scheduling, Reels and Stories").title,
    icon: CalendarClock,
    size: "l",
    href: "/features/publishing",
    visual: "publishing",
    body: "Posts, carousels, Reels and Stories on a calendar, with AI captions and hashtag ideas. Add collaborators to a post or Reel.",
  },
  {
    id: "insight",
    title: "Comment intelligence",
    icon: MessageSquareText,
    size: "m",
    href: "/features/comment-intelligence",
    visual: "insight",
    body: "Sentiment, topics and a summary for every post, with spam hidden automatically if you choose.",
  },
  {
    id: "analytics",
    title: "Analytics and the weekly report",
    icon: ChartLine,
    size: "m",
    href: "#d-insight",
    visual: "analytics",
    body: "Reply rate, first-response time and what customers asked about, plus an email every Monday at 9:00 AM your time.",
  },
  {
    id: "ask",
    title: `Ask ${SITE_NAME}`,
    icon: MessageCircleQuestionMark,
    size: "m",
    ai: true,
    href: "#d-ask",
    visual: "ask",
    body: "Ask about your own business data in plain words. It never sends, changes or deletes anything by itself.",
  },
  {
    id: "team",
    title: "Team roles and assignment",
    icon: UsersRound,
    size: "s",
    href: "#d-team",
    body: "Owners, admins and agents, with conversations assigned by hand or in turn. A team starts on Pro.",
  },
  {
    id: "notifications",
    title: "Notifications, on your phone too",
    icon: BellRing,
    size: "s",
    href: "#d-team",
    body: "In the app, by email and as push notifications when a conversation needs you or a lead arrives.",
  },
  {
    id: "widget",
    title: "Website chat widget",
    icon: PanelsTopLeft,
    platform: "web",
    size: "s",
    href: "#d-inbox",
    body: integration("Website chat").body,
  },
  {
    id: "facebook",
    title: "Facebook Pages",
    icon: Inbox,
    platform: "facebook",
    size: "s",
    status: "approval",
    href: "#d-inbox",
    body: integration("Facebook Pages").body,
  },
  {
    id: "catalogue",
    title: "Catalogue and payment links",
    icon: ShoppingBag,
    size: "s",
    status: "pro",
    href: "#d-selling",
    body: "Products by hand or CSV, so the AI answers price and stock, and payment links sent in the chat.",
  },
  {
    id: "sequences",
    title: feature("Sequences, and broadcasts soon").title,
    icon: Timer,
    size: "s",
    status: "soon",
    href: "#d-automations",
    body: "Timed follow-ups that stop when they reply. WhatsApp broadcasts are coming soon.",
  },
  {
    id: "integrations",
    title: "Integrations and the API",
    icon: Plug,
    size: "s",
    href: "/developers/api",
    body: "Google Sheets, Zapier and the public API on Pro and Max, webhooks on every plan. Shopify follows our app listing.",
  },
  {
    id: "security",
    title: "Security and privacy",
    icon: ShieldCheck,
    size: "s",
    href: "/security",
    body: "No passwords asked, encrypted tokens, and every workspace kept separate.",
  },
];

// ---------------------------------------------------------------- /features: the details

/** One plan limit: a label and Free, Pro and Max. */
export type Limit = { label: string; free: string; pro: string; max: string };

export type DetailGroup = {
  id: string;
  title: string;
  icon: LucideIcon;
  ai?: boolean;
  status?: CellStatus;
  body: string;
  points: string[];
  limits?: Limit[];
  links?: { label: string; href: string }[];
};

const row = (label: string, key: keyof typeof E, format: (v: number | boolean | null) => string = (v) => has(v)): Limit => {
  const values = E[key] as unknown as Record<"free" | "pro" | "max", number | boolean | null>;
  return { label, free: format(values.free), pro: format(values.pro), max: format(values.max) };
};

export const DETAILS: DetailGroup[] = [
  {
    id: "d-inbox",
    title: "The inbox and its channels",
    icon: Inbox,
    body: "Every conversation from Instagram, WhatsApp and your website lands in one inbox, tagged and sorted, with the AI's draft beside it. Instagram and WhatsApp connect only through Meta's official APIs, and we never ask for your password.",
    points: [
      integration("Instagram").body,
      integration("WhatsApp").body,
      `${integration("Website chat").body} You paste one line of code into your site.`,
      `Facebook Pages, with Meta's approval: ${integration("Facebook Pages").body}`,
      `Live comments and ads, with Meta's approval: ${integration("Live comments and ads").body}`,
    ],
    limits: [
      row("Accounts per platform", "accounts_per_platform"),
      row("New website chats a day", "widget_conversations_daily"),
      row("Message history", "message_history_days", (v) => (v === null ? "No limit" : `${limit(v as number)} days`)),
    ],
    links: [{ label: "The AI inbox", href: "/features/ai-inbox" }],
  },
  {
    id: "d-ai",
    title: "AI replies and your knowledge",
    icon: MessageSquareReply,
    ai: true,
    body: FAQ_MADE_UP.answer,
    points: [
      "Off, Suggest or Auto for each account. Suggest drafts a reply for you to send. Auto replies by itself when it is confident, and is part of Pro.",
      "Refunds, legal threats, complaints, abuse, low confidence, or your own phrases go to Needs you. Replying yourself pauses the AI.",
      "The AI writes in the tone you pick, with your emoji level, your do's and don'ts and your sign-off.",
      "Reading a message uses one AI credit, a draft or an automatic reply two, and a test question one.",
    ],
    limits: [
      row("AI credits a month", "ai_credits_monthly"),
      row("AI modes", "ai_modes", (v) => ((v as unknown as string[]).includes("auto") ? "Off, Suggest, Auto" : "Off, Suggest")),
      row("Knowledge, in characters", "knowledge_characters"),
      row("Website pages read", "crawl_pages"),
    ],
    links: [{ label: "The Instagram DM auto-reply guide", href: "/guides/instagram-dm-auto-replies" }],
  },
  {
    id: "d-automations",
    title: "Automations",
    icon: Workflow,
    body: "Turn comments into conversations, the way Instagram allows. Replies are queued to stay within Instagram's sending limits, so a busy post is handled safely.",
    points: [
      "One post, all posts or the next post; a keyword or any comment; public reply variations.",
      "The DM opens with a button, and the link follows their tap. A follow nudge is never a condition for getting the link.",
      "A step editor with quick replies, questions, branches, delays and a split.",
      "Timed follow-ups after a lead is captured or a tag is added, stopping when they reply.",
      "WhatsApp broadcasts are built and open after our review of consent rules.",
    ],
    limits: [
      row("Active automations", "active_automations"),
      row("AI replies in automations", "ai_reply_automations"),
      row("Steps in a flow", "flow_steps"),
      row("Active sequences", "active_sequences"),
    ],
    links: [
      { label: "The comment-to-DM guide", href: "/guides/comment-to-dm-automations" },
      { label: "How sending stays safe", href: "/safety" },
    ],
  },
  {
    id: "d-publishing",
    title: "Scheduling and publishing",
    icon: CalendarClock,
    body: "Compose once and schedule. A Story is a single photo that disappears after 24 hours.",
    points: [
      "Images, carousels, Reels and Stories, on a calendar with week, month and list views, a posting queue and posting times.",
      "Draft a caption or hashtags with AI, then edit them. Each uses one AI credit.",
      "A media library: upload once and reuse.",
      "Add Instagram collaborators to a post or Reel.",
      "Publishing to a Facebook Page is built and waits on Meta's approval.",
    ],
    limits: [row("Scheduled posts a month", "scheduled_posts_monthly")],
    links: [{ label: "Publishing", href: "/features/publishing" }],
  },
  {
    id: "d-insight",
    title: "Comment intelligence, analytics and the weekly report",
    icon: ChartLine,
    body: feature("Analytics and the weekly report").body,
    points: [
      "Each comment is marked as a question, a buying signal or spam, with its sentiment.",
      "A short summary and the main topics for each post, and how many comments still need a reply.",
      // notify/digest.py: Monday 09:00 in the workspace's time zone.
      "The weekly email covers messages received, reply rate, first response, the share the AI handled, the top questions and what still needs you.",
    ],
    limits: [row("Posts with comment intelligence", "comment_intelligence_posts", (v) => (v === null ? "Every post" : `Latest ${limit(v as number)}`))],
    links: [{ label: "Comment intelligence", href: "/features/comment-intelligence" }],
  },
  {
    id: "d-ask",
    title: `Ask ${SITE_NAME}`,
    icon: MessageCircleQuestionMark,
    ai: true,
    body: feature(`Ask ${SITE_NAME}`).body,
    points: [
      "Ask about your own posts, comments and conversations in plain words.",
      "Answers cite the figures they used, and anything it prepares waits for your approval.",
      "It never sends, changes or deletes anything by itself. Answers use AI credits.",
    ],
  },
  {
    id: "d-team",
    title: "Team, notifications and the app",
    icon: UsersRound,
    body: feature("Team roles and assignment").body,
    points: [
      "Assign conversations, reuse saved replies and send an away message outside business hours.",
      feature("Notifications, on your phone too").body,
      "Install it as an app from the browser to get push notifications. On iPhone, add it to your Home Screen first (iOS 16.4 or later).",
    ],
    limits: [row("Team members", "members")],
  },
  {
    id: "d-selling",
    title: "Catalogue, orders and payment links",
    icon: ShoppingBag,
    status: "pro",
    body: feature("Product catalogue, orders and payment links").body,
    points: [
      "Orders are tracked in the Orders page.",
      "Razorpay payment links and UPI requests in the chat, for businesses in India. The money goes to your own account, never through us.",
      "Product messages in WhatsApp need your Meta catalogue set up and Meta's approval.",
      "Shopify sync arrives with our Shopify app listing.",
    ],
    limits: [row("Products", "catalogue_products"), row("Orders a month", "orders_monthly")],
  },
  {
    id: "d-integrations",
    title: "Integrations and the public API",
    icon: Plug,
    body: "Connect to other tools with Zapier, webhooks and API keys.",
    points: [
      "Webhooks on every plan.",
      "Send leads to a spreadsheet you own with Google Sheets, on Pro and Max.",
      "Zapier and the public API, on Pro and Max.",
      "Shopify: bring your products in and keep prices and stock in step, with our Shopify app listing.",
    ],
    limits: [row("Webhook endpoints", "webhook_endpoints"), row("Google Sheets", "sheets_sync"), row("Public API", "public_api")],
    links: [{ label: "The public API", href: "/developers/api" }],
  },
  {
    id: "d-security",
    title: "Security and privacy",
    icon: ShieldCheck,
    body: "What protects your accounts and your customers' messages today.",
    points: TRUST_POINTS.map((point) => `${point.title}: ${point.body}`),
    links: [
      { label: "Security", href: "/security" },
      { label: "Safety", href: "/safety" },
      { label: "Privacy policy", href: "/privacy" },
    ],
  },
];
