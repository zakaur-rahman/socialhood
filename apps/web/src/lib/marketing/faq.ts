import { SUPPORT_EMAIL } from "@/lib/copy";

import table from "./plan-table.json";

export type FaqItem = { question: string; answer: string };

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
export const FAQ_PASSWORD: FaqItem = {
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
// don't lists, sign-off. Free has Off and Suggest; Auto is Pro (plan-table.json ai_modes).
export const FAQ_ROBOTIC: FaqItem = {
  question: "Will the replies sound robotic?",
  answer:
    "The AI writes from your own notes and knowledge, in the tone you pick, with your emoji level, your do's and don'ts and your sign-off. On Free it suggests replies that you edit and send. Comment-to-DM automations send exactly the words you write.",
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
  answer: `Your inbox keeps working. Free runs ${LIMITS.active_automations.free} automations at once, so pause one to turn on another, and schedules ${LIMITS.scheduled_posts_monthly.free} posts a month. When the month's ${count.format(LIMITS.ai_credits_monthly.free)} AI credits are used, AI features pause until they reset, and the app tells you at 80% and 100%. Free keeps messages for ${LIMITS.message_history_days.free} days. Pro raises every limit.`,
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

/** The landing page's questions: the product guide's "Common questions", plus its WhatsApp costs. */
export const FAQ: FaqItem[] = [
  {
    question: "Can Amplychat reply to my customers automatically?",
    answer:
      "Yes. With Auto mode (Pro), the AI replies by itself when it's confident, using your knowledge base. Anything it isn't sure about goes to \"Needs you\" for a person to answer. On Free, the AI suggests replies and you send them.",
  },
  FAQ_MADE_UP,
  FAQ_PROFESSIONAL,
  FAQ_PASSWORD,
  FAQ_TAKEOVER,
  {
    question: "Can I connect more than one Instagram account?",
    answer: "Yes. Free includes 1 account per platform, and Pro includes 3.",
  },
  {
    question: "Why can't I message a customer who wrote to me days ago?",
    answer:
      "Instagram only allows businesses to message a customer within 24 hours of the customer's last message. Once they write again, you can reply. Amplychat shows when this window closes.",
  },
  FAQ_BAN_RISK,
  {
    question: "Can my automation require people to follow me before sending the link?",
    answer:
      "No. Instagram's rules don't allow making a follow a condition. Amplychat can politely invite people to follow, and it always sends what they asked for.",
  },
  {
    question: "Does Amplychat post to my account without asking?",
    answer:
      "No. It only publishes posts you create and schedule. Ask Amplychat never publishes, sends or changes anything by itself.",
  },
  {
    question: "Is there a mobile app?",
    answer:
      "Amplychat works in any modern browser on phone and computer, and you can install it as an app from the browser to get push notifications. On iPhone, add it to your Home Screen first (iOS 16.4 or later).",
  },
  {
    question: "What happens when I run out of AI credits?",
    answer: "AI features pause until your credits reset or you upgrade. Everything else keeps working.",
  },
  FAQ_WHATSAPP_FEES,
  {
    question: "Can I cancel anytime?",
    answer: "Yes. Pro stays active until the end of the period you've paid for, then your workspace moves to Free.",
  },
  {
    question: "How do I contact support?",
    answer: `Email ${SUPPORT_EMAIL}.`,
  },
];
