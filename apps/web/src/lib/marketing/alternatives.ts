/**
 * "Manychat alternatives" (C-163): /compare/manychat-alternatives, a list page built only from what
 * the comparison pages already say (lib/marketing/gtm-pages.ts, read on the dates their sources
 * give). Rules, as on the comparisons:
 *
 * - Every line about a vendor restates a cell or "Which fits you" line on that vendor's comparison
 *   page; the comment above it names the row. Nothing new is claimed about anyone.
 * - Listed in alphabetical order, and the page says the order isn't a ranking. No "best", no "#1",
 *   no scores. Amplychat is listed like the others, with its limits.
 * - Prices are the vendor's own, as recorded on its comparison page, with the date read. No price of
 *   ours is written: ours comes from the plan list on /pricing.
 */

import {
  COMPARE_AISENSY,
  COMPARE_CREATORFLOW,
  COMPARE_INRO,
  COMPARE_INSTANTDM,
  COMPARE_INTERAKT,
  COMPARE_LINKDM,
  COMPARE_MANYCHAT,
  COMPARE_SPUR,
  COMPARE_WATI,
  type GtmPage,
} from "./gtm-pages";
import { latestChecked } from "./competitor-note";
import { SITE_NAME } from "./site";

export const ALTERNATIVES_PATH = "/compare/manychat-alternatives";
/** When this page's copy last changed. */
export const ALTERNATIVES_UPDATED = "2026-10-31";

export type Alternative = {
  name: string;
  /** "instagram", "whatsapp" or both: the channel marks on the card. */
  channels: ("instagram" | "whatsapp" | "web")[];
  /** One line: who it suits. */
  bestFor: string;
  strengths: string[];
  limits: string[];
  /** The starting price as recorded on the comparison page (theirs), or our plan line. */
  price: string;
  /** The full comparison; for Amplychat, the comparison with Manychat. */
  href: string;
  linkLabel: string;
  /** The comparison page the lines come from, for the date its sources were read. */
  page: GtmPage;
  ours?: boolean;
};

/** A row's text on a comparison page ("theirs", or "ours" for Amplychat). */
function cell(page: GtmPage, feature: string, side: "ours" | "theirs" = "theirs"): string {
  const row = page.compare?.rows.find((item) => item.feature === feature);
  const text = row?.[side].text;
  if (!text) throw new Error(`${page.path}: no "${feature}" text`);
  return text;
}

export const ALTERNATIVES: Alternative[] = [
  {
    name: "AiSensy",
    channels: ["whatsapp"],
    // COMPARE_AISENSY "Which fits you"
    bestFor: "Businesses whose main channel is WhatsApp and who want broadcasts, chatbots and selling in WhatsApp.",
    strengths: [
      // rows: Broadcasts, Chatbot flows, Catalogue and payments
      "WhatsApp broadcasts, with scheduling on the Pro plan.",
      "A drag-and-drop chatbot builder, as an add-on.",
      "A WhatsApp catalogue and payments by UPI and card.",
    ],
    limits: [
      // rows: Channels, Instagram comment to DM (not found)
      "Instagram messaging and comment-to-DM weren't on the pages we read.",
      // rows: Chatbot flows, AI answers from your knowledge
      "The chatbot builder and the AI agent builder are paid add-ons.",
    ],
    price: cell(COMPARE_AISENSY, "How it is priced"),
    href: COMPARE_AISENSY.path,
    linkLabel: COMPARE_AISENSY.name,
    page: COMPARE_AISENSY,
  },
  {
    name: SITE_NAME,
    channels: ["instagram", "whatsapp", "web"],
    // COMPARE_MANYCHAT "Which fits you" (ours)
    bestFor: "Businesses and creators who want Instagram, WhatsApp and website chat in one inbox, with AI that answers from their own knowledge.",
    strengths: [
      // OURS_CHANNELS, OURS_AI
      "Instagram, WhatsApp and a website chat widget in one inbox.",
      "AI that answers only from your documents, Q&A, products and website pages, with hand-off to a person.",
      // OURS_COMMENT_ANALYSIS, OURS_PUBLISHING
      "Comment analysis for each post, and Instagram publishing from a calendar.",
      // OURS_PRICE
      "Plans cap features, never contacts.",
    ],
    limits: [
      // SWITCH_PAGE "What is different": no free-form canvas, triggers we don't have, channels
      "No free-form flow canvas, and no share-to-DM or follow triggers.",
      // OURS_BROADCASTS, OURS_CHANNELS
      "WhatsApp broadcasts are coming soon, and Facebook Pages and Messenger wait on Meta's approval.",
      "No TikTok, Telegram, SMS or email channels.",
    ],
    // OURS_PRICE (no price of ours is written; the pricing page reads the plan list)
    price: "A Free plan with no card. See the pricing page for Pro.",
    href: COMPARE_MANYCHAT.path,
    linkLabel: COMPARE_MANYCHAT.name,
    page: COMPARE_MANYCHAT,
    ours: true,
  },
  {
    name: "CreatorFlow",
    channels: ["instagram"],
    // COMPARE_CREATORFLOW "Which fits you"
    bestFor: "Creators who send links from comments and Stories with messages they write themselves.",
    strengths: [
      // rows: Comment to DM and Story replies, Follow gate and email gate, Analytics
      "Comment-to-DM and Story replies on every plan, with unlimited keyword triggers.",
      "A follow gate and an email gate on Pro and Growth.",
      "Link clicks, leads and conversions, with clicks by country.",
    ],
    limits: [
      // rows: Channels, AI replies (not found), Inbox and contacts (not found)
      "Instagram only.",
      "AI replies weren't found: its home page says you write every message.",
      "A DM inbox wasn't described on the pages we read.",
    ],
    price: cell(COMPARE_CREATORFLOW, "How it is priced"),
    href: COMPARE_CREATORFLOW.path,
    linkLabel: COMPARE_CREATORFLOW.name,
    page: COMPARE_CREATORFLOW,
  },
  {
    name: "Inrō",
    channels: ["instagram"],
    // COMPARE_INRO "Which fits you" and intro
    bestFor: "Instagram-only brands that want an AI agent, DM campaigns to segments and a CRM.",
    strengths: [
      // rows: AI answers from your knowledge, Broadcasts and DM campaigns, Integrations
      "An AI agent trained on your site, FAQ and price list, that pulls you in when it matters.",
      "Instagram DM campaigns to a segment: 3 a month on Free, unlimited on Pro.",
      "Shopify, Calendly, Stripe and Make, with webhooks, an API and MCP on Pro.",
    ],
    limits: [
      // rows: Channels, How it is priced, Comment analysis (not found), Publishing (not found)
      "Built only for Instagram.",
      "Priced by activated contacts.",
      "Comment analysis and post scheduling weren't found on the pages we read.",
    ],
    price: cell(COMPARE_INRO, "How it is priced"),
    href: COMPARE_INRO.path,
    linkLabel: COMPARE_INRO.name,
    page: COMPARE_INRO,
  },
  {
    name: "InstantDM",
    channels: ["instagram"],
    // COMPARE_INSTANTDM "Which fits you"
    bestFor: "Accounts that work on Instagram alone and want a low price and timed follow-ups.",
    strengths: [
      // rows: Lead capture and follow-ups, Publishing posts, Comment to DM, Stories and Live
      "Email and phone capture, and DM sequences of up to 10 messages with delays.",
      "Schedule posts and Reels with the auto-DM attached.",
      "Triggers on posts and Reels, Story replies and mentions, and Live comments.",
    ],
    limits: [
      // rows: Channels, AI replies, Inbox and contacts
      "WhatsApp is listed as a support channel, not a messaging channel.",
      "The AI agent step runs on your own OpenAI, Claude, Gemini or DeepSeek key.",
      "Team tools are on the Multi Pro plan.",
    ],
    price: cell(COMPARE_INSTANTDM, "How it is priced"),
    href: COMPARE_INSTANTDM.path,
    linkLabel: COMPARE_INSTANTDM.name,
    page: COMPARE_INSTANTDM,
  },
  {
    name: "Interakt",
    channels: ["whatsapp", "instagram"],
    // COMPARE_INTERAKT "Which fits you"
    bestFor: "Businesses built around WhatsApp campaigns to a list, with a catalogue and checkout inside WhatsApp.",
    strengths: [
      // rows: Bulk WhatsApp campaigns, Product catalogue, Payments and checkout in chat
      "One-time and ongoing campaigns, with click and conversion tracking from the Growth plan.",
      "Catalogue creation, product message templates and Shopify catalogue sync, from the Growth plan.",
      "Payment links from the inbox, and a WhatsApp checkout bot with WhatsApp Pay from the Growth plan.",
    ],
    limits: [
      // rows: AI answers from your knowledge, Comment analysis (not found), Publishing (not found)
      "WhatsApp AI agents are a paid add-on on the Growth and Advanced plans.",
      "Comment analysis and post publishing weren't found on its pricing page.",
    ],
    price: cell(COMPARE_INTERAKT, "Starting price"),
    href: COMPARE_INTERAKT.path,
    linkLabel: COMPARE_INTERAKT.name,
    page: COMPARE_INTERAKT,
  },
  {
    name: "LinkDM",
    channels: ["instagram"],
    // COMPARE_LINKDM "Which fits you"
    bestFor: "Creators and brands that mainly send links from comments and Stories and want a free or low-cost start.",
    strengths: [
      // rows: How it is priced, Share to DM, Lead capture
      "A Free plan for up to 1,000 DMs a month.",
      "A share-to-inbox trigger on every plan.",
      "Email capture in chat on Pro, with lead forms sent to Kit and Flodesk.",
    ],
    limits: [
      // rows: Channels, AI answers (not found), Team inbox (not found)
      "Instagram and Facebook only; its FAQ says it works only with those two.",
      "AI replies and a shared team inbox weren't found on the pages we read.",
    ],
    price: cell(COMPARE_LINKDM, "How it is priced"),
    href: COMPARE_LINKDM.path,
    linkLabel: COMPARE_LINKDM.name,
    page: COMPARE_LINKDM,
  },
  {
    name: "Spur",
    channels: ["whatsapp", "instagram", "web"],
    // COMPARE_SPUR "Which fits you"
    bestFor: "Shopify stores that want WhatsApp, Instagram and website chat in one inbox with an AI agent.",
    strengths: [
      // rows: Shopify and catalogue, Broadcasts, AI answers from your knowledge
      "A Shopify app that syncs customers, orders and products, and WooCommerce.",
      "Unlimited WhatsApp broadcasts to segments on every plan.",
      "AI agents trained on your product catalogue, website and FAQs, with hand-off to a person.",
    ],
    limits: [
      // rows: How it is priced, Flows, Shopify and catalogue
      "Spur's own page says there is no free plan; each plan has a 14-day trial.",
      "The AI Acquire plan has no WhatsApp automation.",
      "A WhatsApp catalogue is a $39 a month add-on.",
    ],
    price: cell(COMPARE_SPUR, "How it is priced"),
    href: COMPARE_SPUR.path,
    linkLabel: COMPARE_SPUR.name,
    page: COMPARE_SPUR,
  },
  {
    name: "Wati",
    channels: ["whatsapp", "instagram", "web"],
    // COMPARE_WATI "Which fits you"
    bestFor: "Businesses that send large WhatsApp broadcasts and need CRM integrations such as HubSpot or Salesforce.",
    strengths: [
      // rows: Broadcasts, AI answers from your knowledge, Channels
      "15,000 broadcasts a month on Growth, unlimited on Pro and Business.",
      "Astra AI agents trained on website pages, documents and Q&A pairs, with hand-off to a teammate.",
      "WhatsApp, calling, Facebook, Instagram, TikTok and web chat in one inbox.",
    ],
    limits: [
      // rows: Team inbox, Integrations, Meta's WhatsApp fees
      "3 users on Growth with no extra users.",
      "Webhooks from the Pro plan.",
      "Template messages are charged on top of the plan, from Wati's rate card.",
    ],
    price: cell(COMPARE_WATI, "How it is priced"),
    href: COMPARE_WATI.path,
    linkLabel: COMPARE_WATI.name,
    page: COMPARE_WATI,
  },
];

/** The competitor names on the page, for the trademark note. */
export const ALTERNATIVE_COMPETITORS = ["Manychat", ...ALTERNATIVES.filter((item) => !item.ours).map((item) => item.name)];

/** The newest date any source behind the page was read on. */
export function alternativesChecked(): string {
  return [COMPARE_MANYCHAT, ...ALTERNATIVES.map((item) => item.page)].reduce((latest, page) => {
    const checked = latestChecked(page) ?? "";
    return checked > latest ? checked : latest;
  }, "");
}

/**
 * Why people look for an alternative, from Manychat's own pages as COMPARE_MANYCHAT records them
 * (help centre and product updates, read 2026-10-29 through a search engine's copy, C-155).
 */
export const WHY_SWITCH: { title: string; body: string }[] = [
  {
    // COMPARE_MANYCHAT "How it is priced" (Manychat help: Pro plan, Active Contacts)
    title: "Billing by active contacts",
    body: "Since 2 March 2026, Manychat's plans are billed by active contacts a month. Pro is $39 a month for 2,500 active contacts on monthly billing, and prices can vary by region.",
  },
  {
    // COMPARE_MANYCHAT "AI answers from your knowledge" (product updates: AI hub beta, Knowledge v2)
    title: "AI that answers from your knowledge",
    body: "Manychat AI is in beta. It replies from links and text you add and can pass uncertain messages to your team. Some teams want that at the centre of the inbox.",
  },
  {
    // COMPARE_MANYCHAT "Comment analysis per post" and "Publishing posts" (not found)
    title: "Comments and posts in one place",
    body: "On Manychat's help centre we found comments used as triggers, but not comment analysis or post scheduling. Some teams want those next to their DMs.",
  },
];

/** Where Manychat is stronger, from its "Which fits you" line on COMPARE_MANYCHAT. */
export const MANYCHAT_STRENGTHS =
  "Manychat may fit better if you need a free-form flow canvas, share-to-DM or follow triggers, or channels such as TikTok, Telegram, SMS and email.";
