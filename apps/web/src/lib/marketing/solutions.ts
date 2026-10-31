/**
 * /for-creators and /for-businesses (C-156): the same structure for two audiences, as data the page
 * renders (components/marketing/SolutionPageView). Rules, as for the GTM pages (gtm-pages.ts): every
 * claim is built and checked against the code (named in a comment where it isn't obvious), a feature
 * that waits on something says so with its status, no prices are written here (Pro's comes from the
 * plans API), and there are no testimonials, user counts or badges. Plan numbers come from
 * plan-table.json, the API's own plan table.
 */
import { SUPPORT_EMAIL } from "@/lib/copy";

import {
  FAQ_BAN_RISK,
  FAQ_FREE_LIMIT,
  FAQ_MADE_UP,
  FAQ_ACCOUNT_LOGIN,
  FAQ_ROBOTIC,
  FAQ_TAKEOVER,
  FAQ_WHATSAPP_FEES,
  type FaqItem,
} from "./faq";
import type { Status } from "./gtm-pages";
import table from "./plan-table.json";
import { SITE_NAME } from "./site";

const E = table.entitlements;
const n = (value: number) => new Intl.NumberFormat("en-US").format(value);

export type Familiar = { before: string; after: string };
export type SolutionFeature = { title: string; body: string; status?: Status };
export type Tier = { name: string; who: string; plan: "free" | "pro"; body: string };

export type SolutionPage = {
  path: string;
  name: string;
  title: string;
  description: string;
  eyebrow: string;
  h1: string;
  intro: string;
  familiar: Familiar[];
  featuresTitle: string;
  featuresIntro: string;
  features: SolutionFeature[];
  /** Show the integrations list with each one's honest status (the landing page's rows). */
  integrations?: boolean;
  tiersIntro: string;
  tiers: Tier[];
  faq: FaqItem[];
  related: { label: string; href: string }[];
};

// ---- Creators

// Built: comment-to-DM with keyword or any comment, one post / all posts / next post, random public
// replies, tap first and the follow invite after the message (C-031), story reply and mention
// triggers with the heart sticker (C-082, C-083), publishing with collaborators (C-134), comment
// intelligence (Free: 5 latest posts per account), Ask (read-only; it prepares drafts, C-126).
// Live comments wait for Meta's approval (C-077).
const FAQ_WHY_PROFESSIONAL: FaqItem = {
  question: "Why do I need a Professional account?",
  answer:
    "Instagram only lets apps read and answer DMs and comments on professional accounts, Business or Creator. Switching is free in the Instagram app's settings, and a Creator account works.",
};

export const FOR_CREATORS: SolutionPage = {
  path: "/for-creators",
  name: "For creators",
  title: "For creators",
  description:
    "Comment-to-DM for link drops and freebies, scheduled posts and Reels, AI replies from your own notes, and comment analysis for Instagram creators.",
  eyebrow: "For creators",
  h1: "Keep up with every comment and DM, and keep creating",
  intro:
    "Send your link to everyone who comments the keyword, schedule what you post, and let AI draft replies from your own notes. You stay in charge of every conversation.",
  familiar: [
    {
      before: "You post a Reel that says “comment LINK”, then spend the evening sending the same link by hand.",
      after: "A comment-to-DM automation sends it to everyone who comments the keyword, within Meta's limits.",
    },
    {
      before: "The same questions about your gear, your rates or your next drop fill your DMs.",
      after: "AI drafts the answer from your own notes, and anything it can't answer comes to you.",
    },
    {
      before: "Hundreds of comments, and no time to read what people are actually asking for.",
      after: "Each post gets a summary of sentiment, topics and questions, with a count of comments that need a reply.",
    },
    {
      before: "Posting happens when you remember, and Stories slip.",
      after: "Posts, carousels, Reels and Stories sit on one calendar and go out on time.",
    },
  ],
  featuresTitle: "What you can do with it",
  featuresIntro: "Everything here is built. A feature that waits on Meta says so.",
  features: [
    {
      title: "Comment-to-DM for link drops",
      body: "Someone comments LINK and gets your link by DM: an affiliate link, a booking page, a freebie or a waitlist. Match a keyword or any comment, on one post, every post or your next one, with varied public replies.",
      status: "yes",
    },
    {
      title: "Tap first, and a follow invite after",
      body: "The first DM asks them to tap a button, and the tap opens the chat for your link. You can add an invite to follow after the link, never instead of it.",
      status: "yes",
    },
    {
      title: "Story replies and mentions",
      body: "A reply to your story can start an automation, with an optional heart reaction, and so can a story that mentions you.",
      status: "yes",
    },
    {
      title: "Scheduling, Reels and Stories",
      body: "Posts, carousels, Reels and Stories on a calendar, with AI captions and hashtag ideas. Add Instagram collaborators to a post or Reel.",
      status: "yes",
    },
    {
      title: "AI replies from your own notes",
      body: "Add your notes, FAQs or your website, and the AI drafts replies in your tone. On Free you send them; Auto mode on Pro replies when it's confident. The rest comes to you.",
      status: "yes",
    },
    {
      title: "Comment analysis",
      body: `Sentiment, topics, buying signals and spam for each post, with a needs-reply count. Free covers your ${E.comment_intelligence_posts.free} latest posts per account.`,
      status: "yes",
    },
    {
      title: `Ask ${SITE_NAME}`,
      body: "Ask about your own messages, comments and posts in plain words. Answers show the numbers they used and link to their sources. It prepares drafts for you to review and never sends, changes or deletes anything by itself.",
      status: "yes",
    },
    {
      title: "Live comments",
      body: "Answer comments made during an Instagram Live. Meta only sends these events to apps it has approved.",
      status: "approval",
    },
  ],
  tiersIntro:
    "Pick by where you are today. Plans cap features, never followers or contacts, so a post that goes viral doesn't change your plan.",
  tiers: [
    {
      name: "Just starting",
      who: "One account and a few link drops a week.",
      plan: "free",
      body: `${E.accounts_per_platform.free} Instagram account, ${E.active_automations.free} automations on at once, AI suggestions with ${n(E.ai_credits_monthly.free)} credits a month, and comment analysis on your ${E.comment_intelligence_posts.free} latest posts.`,
    },
    {
      name: "Growing",
      who: "A link drop on most posts and DMs every day.",
      plan: "pro",
      body: `Auto replies, up to ${E.active_automations.pro} automations on at once, ${n(E.ai_credits_monthly.pro)} AI credits a month and ${E.scheduled_posts_monthly.pro} scheduled posts a month. Start on Free and move up when you need it.`,
    },
    {
      name: "Established",
      who: "More than one account, with a manager or an assistant.",
      plan: "pro",
      body: `${E.accounts_per_platform.pro} accounts per platform, ${E.members.pro} team members, comment analysis on every post and your full message history.`,
    },
  ],
  faq: [FAQ_BAN_RISK, FAQ_ACCOUNT_LOGIN, FAQ_WHY_PROFESSIONAL, FAQ_ROBOTIC, FAQ_TAKEOVER, FAQ_FREE_LIMIT],
  related: [
    { label: "Safety: Meta's limits and how we send", href: "/safety" },
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "Publishing", href: "/features/publishing" },
    { label: "Switch from Manychat", href: "/switch-from-manychat" },
    { label: "Plans and limits", href: "/pricing" },
  ],
};

// ---- Businesses

// Built: the inbox for Instagram, WhatsApp and website chat (C-150), assignment (GR-20), saved
// replies and business hours with away messages (GR-21, GR-22), AI modes with escalation and
// knowledge gaps, website crawl (GR-35), intent, sentiment and lead score on every message, the
// leads list (GR-18), catalogue, orders and payment links on Pro (GR-31, GR-32), Sheets on Pro (GR-26).
export const FOR_BUSINESSES: SolutionPage = {
  path: "/for-businesses",
  name: "For businesses",
  title: "For businesses",
  description:
    "One inbox for Instagram, WhatsApp and website chat, AI replies from your own knowledge with hand-off to your team, lead scores and payment links.",
  eyebrow: "For businesses",
  h1: "Every customer message, answered from one inbox",
  intro:
    "Instagram, WhatsApp and your website chat in one place. AI answers from what you've taught it, and hands refunds, complaints and anything it doesn't know to your team.",
  familiar: [
    {
      before: "Customers write on Instagram, WhatsApp and your website, and you check three apps.",
      after: "One inbox for all three, sorted so what needs a person comes first.",
    },
    {
      before: "The same questions about price, stock and delivery, all day long.",
      after: "AI answers from your price list, FAQs and website, and lists what it couldn't answer.",
    },
    {
      before: "Messages that arrive after closing wait until morning.",
      after: "Business hours with an away message, and AI replies when it's confident.",
    },
    {
      before: "An upset customer gets a cheerful automatic reply.",
      after: "Refunds, complaints and legal threats always go to a person.",
    },
    {
      before: "You can't tell who is ready to buy.",
      after: "Every message is tagged with intent and sentiment, and leads get a score.",
    },
  ],
  featuresTitle: "What runs your conversations",
  featuresIntro: "Everything here is built. Where a plan or Meta's approval is needed, it says so.",
  features: [
    {
      title: "One inbox, with your team",
      body: "Instagram DMs and comments, WhatsApp and your website chat in one list. Assign conversations by hand or in turn, use saved replies, and set business hours with an away message. Teams start on Pro.",
      status: "yes",
    },
    {
      title: "AI from your knowledge, with hand-off",
      body: "Teach it with documents, FAQs or a crawl of your website. Choose Off, Suggest or Auto for each account. It hands over refunds, complaints, legal threats and anything it can't answer from your knowledge, and lists those questions so you can fill the gaps.",
      status: "yes",
    },
    {
      title: "Lead scoring",
      body: "Every message is tagged with intent and sentiment and gets a lead score. Ask for an email or phone in a flow, see your leads in one list, and send them to Google Sheets on Pro.",
      status: "yes",
    },
    {
      title: "Catalogue, orders and payment links",
      body: "Add products by hand or CSV, and the AI answers price and stock. Send a Razorpay payment link or a UPI request in the chat, from your own Razorpay account; the money goes to you, never through us. Part of Pro.",
      status: "yes",
    },
    {
      title: "Automations and follow-ups",
      body: "Comment-to-DM and DM keyword automations, flows that ask questions and branch, and timed follow-ups that stop when the customer replies.",
      status: "yes",
    },
    {
      title: "Reports",
      body: "Messages received, reply rate, first-response time and what customers asked about, with a summary email every Monday.",
      status: "yes",
    },
  ],
  integrations: true,
  tiersIntro: "Pick by where you are today. Plans cap features, never how many contacts you have.",
  tiers: [
    {
      name: "Just starting",
      who: "One person answering, on one Instagram and one WhatsApp.",
      plan: "free",
      body: `${E.accounts_per_platform.free} account per platform, ${E.members.free} seat, AI suggestions with ${n(E.ai_credits_monthly.free)} credits a month, and website chat for up to ${E.widget_conversations_daily.free} conversations a day.`,
    },
    {
      name: "Growing",
      who: "Chats every hour, and a teammate or two.",
      plan: "pro",
      body: `Auto replies, ${E.members.pro} team members, ${n(E.ai_credits_monthly.pro)} AI credits a month, the catalogue and payment links, Google Sheets and the public API.`,
    },
    {
      name: "Established",
      who: "Several brands or numbers, and a bigger team.",
      plan: "pro",
      body: `${E.accounts_per_platform.pro} accounts per platform today. A larger plan for bigger teams is planned and can't be bought yet.`,
    },
  ],
  faq: [
    FAQ_WHATSAPP_FEES,
    FAQ_MADE_UP,
    FAQ_TAKEOVER,
    {
      question: "Can my team share the inbox?",
      answer: `Yes, on Pro: up to ${E.members.pro} team members with owner, admin and agent roles, and conversations assigned by hand or in turn. Free has ${E.members.free} seat.`,
    },
    {
      question: "Does it work with Shopify?",
      answer:
        "Shopify sync arrives with our Shopify app listing. Until then, add products by hand or from a CSV file on Pro, and the AI answers price and stock from them.",
    },
    FAQ_ACCOUNT_LOGIN,
    FAQ_FREE_LIMIT,
  ],
  related: [
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "Safety: Meta's limits and how we send", href: "/safety" },
    { label: "Amplychat vs Interakt", href: "/compare/interakt" },
    { label: "Plans and limits", href: "/pricing" },
    { label: `Questions? ${SUPPORT_EMAIL}`, href: `mailto:${SUPPORT_EMAIL}` },
  ],
};
