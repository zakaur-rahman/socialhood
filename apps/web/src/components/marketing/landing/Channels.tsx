import type { Route } from "next";
import { type LucideIcon, Radio, Sheet, ShoppingCart, Wallet, Webhook } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import type { Platform } from "@/lib/api/types";
import { SECTION_IDS } from "@/lib/marketing/site";

import { Ico } from "./Ico";

type Integration = {
  name: string;
  body: string;
  /** What is true today, in a few words (C-122, C-138). */
  status: string;
  tone: "live" | "waiting" | "yours";
  /** A channel's own mark, drawn in its colour (the page's motif); other rows get an icon (C-157 motion). */
  mark?: string;
  platform?: Platform;
  icon?: LucideIcon;
  /** A guide that explains it (LP-4.10). */
  guide?: { label: string; href: string };
};

// One line each, and the honest status: what runs today, what waits for Meta's approval, what
// arrives with our Shopify app listing, and what is yours (C-108, C-111, C-116, C-120, C-122).
// Instagram's post insights need a permission production doesn't ask for yet
// (IG_REQUEST_INSIGHTS_SCOPE), so they are worded as waiting (C-155).
export const INTEGRATIONS: Integration[] = [
  {
    name: "Instagram",
    body: "DMs, comments and publishing for Business and Creator accounts, with Instagram's own login. Post insights follow Meta's approval.",
    status: "Official API",
    tone: "live",
    mark: "var(--ig)",
    platform: "instagram",
  },
  {
    name: "WhatsApp",
    body: "A WhatsApp Business number your business owns, through Meta's Embedded Signup. Meta bills its fees to you.",
    guide: { label: "The WhatsApp Business API, explained", href: "/guides/whatsapp-business-api-vs-app" },
    status: "Official API",
    tone: "live",
    mark: "var(--wa)",
    platform: "whatsapp",
  },
  {
    name: "Website chat",
    body: "A chat widget for your own site that answers from your knowledge, in the same inbox.",
    status: "On every plan",
    tone: "live",
    mark: "var(--web)",
    platform: "web",
  },
  {
    name: "Facebook Pages",
    body: "Messenger chats and Page comments in the same inbox, and publishing to your Page.",
    status: "With Meta's approval",
    tone: "waiting",
    mark: "var(--fb)",
    platform: "facebook",
  },
  {
    // C-157 (organize): shortened from "Live comments and ad replies" so it fits one line in a card; the
    // line below still says what it answers.
    name: "Live comments and ads",
    icon: Radio,
    body: "Answer comments made during an Instagram Live, and chats that start from an ad.",
    status: "With Meta's approval",
    tone: "waiting",
  },
  {
    name: "Shopify",
    icon: ShoppingCart,
    body: "Bring your products in and keep prices and stock in step.",
    status: "With our Shopify app listing",
    tone: "waiting",
  },
  {
    name: "Google Sheets",
    icon: Sheet,
    body: "Send leads to a spreadsheet you own, as they arrive.",
    status: "Pro and Max",
    tone: "yours",
  },
  {
    name: "Zapier and the public API",
    icon: Webhook,
    body: "Connect to other tools with Zapier, webhooks and API keys.",
    status: "Pro and Max",
    tone: "yours",
  },
];

/**
 * Payments, as one quiet line under the connections (C-157): India's rails, not a headline item on
 * a global page. Built: razorpay/ (payment links, UPI requests), to the business's own account.
 */
export const PAYMENTS = "Razorpay payment links and UPI requests in the chat, for businesses in India. The money goes to your own account, never through us.";

const DOT = { live: "var(--ok)", waiting: "var(--wait-mark)", yours: "var(--iris)" } as const;

/**
 * What Amplychat connects to (C-155), inside the Features section since C-157: a strict grid of
 * equal-height cards (the mark and name, one line, a guide when there is one, and the honest status
 * pinned to the card's foot so statuses line up across a row), then payments as one full-width row.
 */
export function Connections() {
  return (
    <div className="conn" id={SECTION_IDS.integrations}>
      <div className="split-head">
        <h3 id="integrations-title" className="h-sec">
          Connects to where your customers are
        </h3>
        <p className="lede">
          Instagram and WhatsApp connect only through Meta&apos;s official APIs, and we never ask for your password. Each one
          says what runs today.
        </p>
      </div>
      <ul className="chan">
        {INTEGRATIONS.map((item) => (
          <li key={item.name} className="crow">
            <h4>
              {item.platform ? (
                <Ico className="ico-mark" style={{ "--c": item.mark } as CSSProperties}>
                  <PlatformGlyph platform={item.platform} />
                </Ico>
              ) : (
                <Ico icon={item.icon} />
              )}
              <span>{item.name}</span>
            </h4>
            <p className="crow-b">{item.body}</p>
            {item.guide ? (
              <p className="crow-g">
                <Link href={item.guide.href as Route}>{item.guide.label}</Link>
              </p>
            ) : null}
            <span className="st" style={{ "--sc": DOT[item.tone] } as CSSProperties}>
              {item.status}
            </span>
          </li>
        ))}
      </ul>
      <p className="pay">
        <b>
          <Ico icon={Wallet} />
          Payments
        </b>
        <span>{PAYMENTS}</span>
      </p>
    </div>
  );
}
