import type { CSSProperties } from "react";

import { SECTION_IDS } from "@/lib/marketing/site";

type Integration = {
  name: string;
  body: string;
  /** What is true today, in a few words (C-122, C-138). */
  status: string;
  tone: "live" | "waiting" | "yours";
  /** The mark beside the name: a platform colour, or none. */
  mark?: string;
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
  },
  {
    name: "WhatsApp",
    body: "A WhatsApp Business number your business owns, through Meta's Embedded Signup. Meta bills its fees to you.",
    status: "Official API",
    tone: "live",
    mark: "var(--wa)",
  },
  {
    name: "Website chat",
    body: "A chat widget for your own site that answers from your knowledge, in the same inbox.",
    status: "On every plan",
    tone: "live",
    mark: "var(--web)",
  },
  {
    name: "Facebook Pages",
    body: "Messenger chats and Page comments in the same inbox, and publishing to your Page.",
    status: "With Meta's approval",
    tone: "waiting",
    mark: "var(--fb)",
  },
  {
    name: "Live comments and ad replies",
    body: "Answer comments made during an Instagram Live, and chats that start from an ad.",
    status: "With Meta's approval",
    tone: "waiting",
  },
  {
    name: "Shopify",
    body: "Bring your products in and keep prices and stock in step.",
    status: "With our Shopify app listing",
    tone: "waiting",
  },
  {
    name: "Razorpay and UPI",
    body: "Payment links and UPI requests in the chat. The money goes to your own account, never through us.",
    status: "Your own account",
    tone: "yours",
  },
  {
    name: "Google Sheets",
    body: "Send leads to a spreadsheet you own, as they arrive.",
    status: "Pro and Max",
    tone: "yours",
  },
  {
    name: "Zapier and the public API",
    body: "Connect to other tools with Zapier, webhooks and API keys.",
    status: "Pro and Max",
    tone: "yours",
  },
];

const DOT = { live: "var(--ok)", waiting: "var(--wait-mark)", yours: "var(--iris)" } as const;

/** What Amplychat connects to, a row each with one line and an honest status (C-155). */
export function Channels() {
  return (
    <section className="sec" id={SECTION_IDS.integrations} aria-labelledby="integrations-title" style={{ paddingTop: 40 }}>
      <div className="wrap">
        <div className="split-head">
          <div>
            <p className="kicker">Integrations</p>
            <h2 id="integrations-title" className="h2">
              Connects to where your customers are
            </h2>
          </div>
          <p className="lede">
            Instagram and WhatsApp connect only through Meta&apos;s official APIs, and we never ask for your password. Each row
            says what runs today.
          </p>
        </div>
        <ul className="chan">
          {INTEGRATIONS.map((item) => (
            <li key={item.name} className="crow">
              <h3 style={item.mark ? ({ "--c": item.mark } as CSSProperties) : undefined}>
                <i aria-hidden />
                {item.name}
              </h3>
              <p>{item.body}</p>
              <span className="st" style={{ "--sc": DOT[item.tone] } as CSSProperties}>
                {item.status}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
