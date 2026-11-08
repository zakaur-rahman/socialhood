import { SUPPORT_EMAIL } from "@/lib/copy";

import table from "./plan-table.json";

/** `link`: a page that says more, shown after the answer (the FAQPage JSON-LD keeps the plain answer). */
export type FaqItem = { question: string; answer: string; link?: { label: string; href: string } };

const LIMITS = table.entitlements;
const count = new Intl.NumberFormat("en-US");

/*
 * Questions shared by the landing page, /for-creators and /for-businesses (C-156). Each answer is
 * checked against the code, named beside it, and is plain text, because the FAQPage JSON-LD repeats
 * it word for word.
 */

// platforms/buckets.py: IG_PRIVATE_REPLY never grants more than 750 in any hour per account; the
// automation queue (services/automations/queue.py) holds the rest and skips comments past
// Instagram's 7-day limit (services/comments/actions.py PRIVATE_REPLY_LIMIT).
export const FAQ_BAN_RISK: FaqItem = {
  question: "Can automations get my Instagram account banned?",
  answer:
    "Amplychat only uses Meta's official API and keeps to Meta's published limits: at most 750 private replies to comments an hour for each account, with the rest queued and sent as the limit allows, and none after Instagram's 7-day window. Meta's rules still apply to what you send, and only Meta decides on restrictions, so no tool can promise an account will never be restricted. Our safety page explains how sending works.",
};

// platforms/instagram/oauth.py: Instagram's own login (OAuth); WhatsApp connects through Meta's
// Embedded Signup. Tokens are stored encrypted (TRUST_POINTS).
export const FAQ_ACCOUNT_LOGIN: FaqItem = {
  question: "Do I have to share my Instagram password?",
  answer:
    "No. You connect with Instagram's own login, and WhatsApp with Meta's sign-up window, and choose what to allow there. Amplychat receives an access token, which it stores encrypted, never your password. You can disconnect an account at any time.",
};

export const FAQ_PROFESSIONAL: FaqItem = {
  question: "Does it work with a personal Instagram account?",
  answer:
    "No. Instagram only allows business tools on professional (Business or Creator) accounts. Switching is free in the Instagram app's settings.",
};

// models/ai.py AiSettings: tone (friendly, professional, playful, concise), emoji level, do and
// don't lists, sign-off. Free has Off and Suggest; Auto is Creator and Business (plan-table.json ai_modes).
export const FAQ_ROBOTIC: FaqItem = {
  question: "Will the replies sound robotic?",
  answer:
    "The AI writes from your own notes and knowledge, in the tone you pick, with your emoji level, your do's and don'ts and your sign-off. On Free it suggests replies that you edit and send. Comment-to-DM automations send exactly the words you write.",
  link: { label: "Instagram comment to DM", href: "/instagram/comment-to-dm" },
};

// services/sending.py human_takeover: a reply from a person (in Amplychat or the native app) pauses
// the AI on that conversation for the workspace's takeover period, 2 hours by default; the choices
// are 30 minutes, 2 hours, 24 hours or until resumed (models/ai.py TAKEOVER_MINUTES).
export const FAQ_TAKEOVER: FaqItem = {
  question: "Can I take over a conversation from the AI?",
  answer:
    "Yes. When you reply yourself, in Amplychat or in the Instagram app, the AI pauses on that conversation for 2 hours by default. You can change the pause to 30 minutes, 24 hours or until you resume the AI. Anything the AI can't answer from your knowledge comes to Needs you.",
};

// plan-table.json (billing/plans.py): Free's caps. jobs/tasks/purge.py deletes Free messages older
// than message_history_days. ai/metering.py notifies owners and admins in the app (not by email) at 80% and 100% of credits.
export const FAQ_FREE_LIMIT: FaqItem = {
  question: "What happens when I reach the Free plan's limits?",
  answer: `Your inbox keeps working. Free runs ${LIMITS.active_automations.free} automations at once, so pause one to turn on another, and schedules ${LIMITS.scheduled_posts_monthly.free} posts a month. When the month's ${count.format(LIMITS.ai_credits_monthly.free)} AI credits are used, AI features pause until they reset, and the app tells you at 80% and 100%. Free keeps messages for ${LIMITS.message_history_days.free} days. Creator and Business raise every limit.`,
};

// Owner decision 2026-10-29 (C-156): customers pay Meta directly through their own WhatsApp
// Business account, with no markup from us.
export const FAQ_WHATSAPP_FEES: FaqItem = {
  question: "Do the plans include WhatsApp's messaging fees?",
  answer:
    "No. Meta charges for some WhatsApp messages, by message type and the recipient's country. You pay Meta directly through your own WhatsApp Business account, and Amplychat adds no markup. These charges are separate from your plan.",
};

export const FAQ_MADE_UP: FaqItem = {
  question: "Will the AI make things up?",
  answer:
    "The AI is instructed to answer only from your knowledge base and your conversation. When the answer isn't there, it doesn't guess: it hands the conversation to you and records the question as a knowledge gap.",
};

export const FAQ_AUTO_REPLY: FaqItem = {
  question: "Can Amplychat reply to my customers automatically?",
  answer:
    "Yes. With Auto mode (Creator and Business), the AI replies by itself when it's confident, using your knowledge base. Anything it isn't sure about goes to \"Needs you\" for a person to answer. On Free, the AI suggests replies and you send them.",
};

export const FAQ_ACCOUNTS: FaqItem = {
  question: "Can I connect more than one Instagram account?",
  answer: "Yes. Free connects any 2 of Instagram, Facebook or web chat, with no WhatsApp. Creator connects 2 Instagram accounts and 1 each of WhatsApp, Facebook and web chat. Business connects 4 Instagram accounts and 3 each of WhatsApp and Facebook.",
};

export const FAQ_24_HOURS: FaqItem = {
  question: "Why can't I message a customer who wrote to me days ago?",
  answer:
    "Instagram only allows businesses to message a customer within 24 hours of the customer's last message. Once they write again, you can reply. Amplychat shows when this window closes.",
};

export const FAQ_FOLLOW_GATE: FaqItem = {
  question: "Can my automation require people to follow me before sending the link?",
  answer:
    "No. Instagram's rules don't allow making a follow a condition. Amplychat can politely invite people to follow, and it always sends what they asked for.",
};

export const FAQ_POSTS: FaqItem = {
  question: "Does Amplychat post to my account without asking?",
  answer:
    "No. It only publishes posts you create and schedule. Ask Amplychat never publishes, sends or changes anything by itself.",
};

export const FAQ_MOBILE: FaqItem = {
  question: "Is there a mobile app?",
  answer:
    "Amplychat works in any modern browser on phone and computer, and you can install it as an app from the browser to get push notifications. On iPhone, add it to your Home Screen first (iOS 16.4 or later).",
};

export const FAQ_CREDITS: FaqItem = {
  question: "What happens when I run out of AI credits?",
  answer: "AI features pause until your credits reset or you upgrade. Everything else keeps working.",
};

export const FAQ_CANCEL: FaqItem = {
  question: "Can I cancel anytime?",
  answer: "Yes. Your paid plan stays active until the end of the period you've paid for, then your workspace moves to Free.",
};

// C-168: the MCP server (docs/architecture/mcp 04-phase-b.md, 05-phase-c.md; connect-ai.ts PLAN_ROWS
// and SAFETY): reading and drafts on every plan, scheduling on Creator and Business, a preview and a yes
// before anything is scheduled, and no messages sent from an AI app. C-169: keyword automations
// from an AI app on Creator and Business; the automation sends, once a person turns it on.
export const FAQ_AI_APPS: FaqItem = {
  question: "Can I use Amplychat from Claude or ChatGPT?",
  answer:
    "Yes. Amplychat has an MCP server, so Claude, ChatGPT and Codex can read your inbox, comments and analytics and draft replies on every plan, and schedule posts and set up keyword automations on Creator and Business. Amplychat requires a preview first and the AI waits for your yes, unless you set your AI app to always allow Amplychat's tools, so keep approvals on for changes. It can't send messages to your customers itself: an automation sends once you've turned it on in Amplychat, and knowledge it adds waits for your approval.",
  link: { label: "How it works with AI apps", href: "/mcp" },
};

export const FAQ_SUPPORT: FaqItem = {
  question: "How do I contact support?",
  answer: `Email ${SUPPORT_EMAIL}.`,
};

/**
 * The landing page's questions (C-157: 8 of them, the ones a visitor asks before signing up, the
 * creator questions among them). /faq has them all and marks them up as FAQPage; / doesn't (C-162:
 * Google wants a repeated question marked up once on the site).
 */
export const FAQ: FaqItem[] = [
  FAQ_AUTO_REPLY,
  FAQ_MADE_UP,
  FAQ_TAKEOVER,
  FAQ_BAN_RISK,
  FAQ_ACCOUNT_LOGIN,
  FAQ_PROFESSIONAL,
  FAQ_FOLLOW_GATE,
  FAQ_WHATSAPP_FEES,
];

/** The /faq page (C-157): every question the site answers, in groups. Its FAQPage JSON-LD lists the same, in order. */
export const FAQ_GROUPS: { id: string; title: string; items: FaqItem[] }[] = [
  { id: "the-ai", title: "The AI", items: [FAQ_AUTO_REPLY, FAQ_MADE_UP, FAQ_ROBOTIC, FAQ_TAKEOVER] },
  {
    id: "instagram-and-whatsapp",
    title: "Instagram and WhatsApp",
    items: [FAQ_PROFESSIONAL, FAQ_ACCOUNT_LOGIN, FAQ_ACCOUNTS, FAQ_24_HOURS, FAQ_BAN_RISK, FAQ_FOLLOW_GATE, FAQ_POSTS],
  },
  { id: "plans", title: "Plans and billing", items: [FAQ_FREE_LIMIT, FAQ_CREDITS, FAQ_WHATSAPP_FEES, FAQ_CANCEL] },
  { id: "the-app", title: "The app and support", items: [FAQ_MOBILE, FAQ_AI_APPS, FAQ_SUPPORT] },
];

/** Every question on /faq, in the page's order. */
export const FAQ_ALL: FaqItem[] = FAQ_GROUPS.flatMap((group) => group.items);

/** Where the full list lives. */
export const FAQ_PATH = "/faq";
