import type { Route } from "next";
import Link from "next/link";

import { SECTION_IDS, SITE_NAME } from "@/lib/marketing/site";

import { Connections } from "./Channels";

/** `href`: the feature's own page, when it has one (LP-4.10). */
type Feature = { title: string; body: string; plan?: string; note?: string; href?: string };

// Every line is in the product guide and built, or says what it waits for (C-122, C-138). The inbox,
// the AI replies, knowledge gaps and the automations have their own sections above.
export const FEATURES: Feature[] = [
  {
    title: "Scheduling, Reels and Stories",
    href: "/features/publishing",
    body: "Posts, carousels, Reels and Stories on a calendar, with AI captions and hashtag ideas. Add Instagram collaborators to a post or Reel.",
  },
  {
    title: "Comment intelligence",
    href: "/features/comment-intelligence",
    body: "Sentiment, topics and a summary for every post. Reply publicly or by DM, and hide spam automatically if you choose.",
  },
  {
    title: `Ask ${SITE_NAME}`,
    body: "Ask about your own business data in plain words. Answers show the numbers and time range they used, with links to their sources. It prepares replies and drafts for you to review.",
    note: "Never sends, changes or deletes anything by itself",
  },
  {
    title: "Analytics and the weekly report",
    body: "Messages received, reply rate, first-response time and what customers asked about, plus a summary email every Monday at 9:00 AM your time.",
  },
  {
    title: "Product catalogue, orders and payment links",
    body: "Add products by hand or CSV, and the AI answers price and stock. Send a payment link in the chat; the money goes to your own account.",
    plan: "Pro",
    note: "Shopify sync arrives with our Shopify app listing.",
  },
  {
    title: "Sequences, and broadcasts soon",
    body: "Timed follow-ups after a lead is captured or a tag is added, stopping when they reply. WhatsApp broadcasts are coming soon, once consent rules are checked.",
  },
  {
    title: "Team roles and assignment",
    body: "Owners, admins and agents, with conversations assigned by hand or in turn. The Free plan has 1 seat, so a team starts on Pro.",
  },
  {
    title: "Notifications, on your phone too",
    body: "In the app, by email and as phone push notifications when a conversation needs you or a lead arrives.",
  },
];

/** Ask Amplychat leads the list (C-157): the one feature that works across everything else. */
const [LEAD, ...REST] = [FEATURES.find((f) => f.title === `Ask ${SITE_NAME}`)!, ...FEATURES.filter((f) => f.title !== `Ask ${SITE_NAME}`)];

/**
 * Everything else in the product, and what it connects to (C-155; C-157 merges Integrations in): Ask
 * Amplychat first and larger, the rest as a list set large with no icons, then the connections with
 * their honest status.
 */
export function Features() {
  return (
    <section className="sec sec-tight" id={SECTION_IDS.features} aria-labelledby="features-title">
      <div className="wrap">
        <div className="split-head">
          <h2 id="features-title" className="h2-sm">
            Everything your customer conversations need
          </h2>
          <p className="lede">From the first comment to the reply that closes the sale, in one place.</p>
        </div>
        <div className="feat-lead after-head">
          <h3>{LEAD.title}</h3>
          <div>
            <p>{LEAD.body}</p>
            {LEAD.note ? <p className="note-line">{LEAD.note}</p> : null}
          </div>
        </div>
        <ul className="more">
          {REST.map(({ title, body, plan, note, href }) => (
            <li key={title} className="mi">
              <h3>
                {href ? <Link href={href as Route}>{title}</Link> : title}
                {plan ? <span className="pl"> · {plan}</span> : null}
              </h3>
              <p>{body}</p>
              {note ? <p className="note-line">{note}</p> : null}
            </li>
          ))}
        </ul>
        <p className="more-links">
          Go deeper: <Link href="/features/ai-inbox">the AI inbox</Link>,{" "}
          <Link href="/features/comment-intelligence">comment intelligence</Link>,{" "}
          <Link href="/features/publishing">publishing</Link>, or <Link href="/compare">how {SITE_NAME} compares</Link>.
        </p>
        <Connections />
      </div>
    </section>
  );
}
