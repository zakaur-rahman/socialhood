import type { Route } from "next";
import {
  ArrowRight,
  BellRing,
  CalendarClock,
  ChartLine,
  Inbox,
  type LucideIcon,
  MessageCircleQuestionMark,
  MessageSquareText,
  ShoppingBag,
  Timer,
  TrendingUp,
  UsersRound,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { FEATURES_PATH, SECTION_IDS, SITE_NAME } from "@/lib/marketing/site";

import { Connections } from "./Channels";
import { Ico } from "./Ico";

/** `href`: the feature's own page, when it has one (LP-4.10). `icon`: its card's icon (C-157 motion). */
type Feature = { title: string; body: string; plan?: string; note?: string; href?: string; icon: LucideIcon };

// Every line is in the product guide and built, or says what it waits for (C-122, C-138). The inbox,
// the AI replies, knowledge gaps and the automations have their own sections above.
export const FEATURES: Feature[] = [
  {
    title: "Scheduling, Reels and Stories",
    href: "/features/publishing",
    icon: CalendarClock,
    body: "Posts, carousels, Reels and Stories on a calendar, with AI captions and hashtag ideas. Add Instagram collaborators to a post or Reel.",
  },
  {
    title: "Comment intelligence",
    href: "/features/comment-intelligence",
    icon: MessageSquareText,
    body: "Sentiment, topics and a summary for every post. Reply publicly or by DM, and hide spam automatically if you choose.",
  },
  {
    title: `Ask ${SITE_NAME}`,
    icon: MessageCircleQuestionMark,
    body: "Ask about your own business data in plain words. Answers show the numbers and time range they used, with links to their sources. It prepares replies and drafts for you to review.",
    note: "Never sends, changes or deletes anything by itself",
  },
  {
    title: "Analytics and the weekly report",
    icon: ChartLine,
    body: "Messages received, reply rate, first-response time and what customers asked about, plus a summary email every Monday at 9:00 AM your time.",
  },
  {
    title: "Product catalogue, orders and payment links",
    icon: ShoppingBag,
    body: "Add products by hand or CSV, and the AI answers price and stock. Send a payment link in the chat; the money goes to your own account.",
    plan: "Pro",
    note: "Shopify sync arrives with our Shopify app listing.",
  },
  {
    title: "Sequences, and broadcasts soon",
    icon: Timer,
    body: "Timed follow-ups after a lead is captured or a tag is added, stopping when they reply. WhatsApp broadcasts are coming soon, once consent rules are checked.",
  },
  {
    title: "Team roles and assignment",
    icon: UsersRound,
    body: "Owners, admins and agents, with conversations assigned by hand or in turn. The Free plan has 1 seat, so a team starts on Pro.",
  },
  {
    title: "Notifications, on your phone too",
    icon: BellRing,
    body: "In the app, by email and as phone push notifications when a conversation needs you or a lead arrives.",
  },
];

/** Ask Amplychat leads the list (C-157): the one feature that works across everything else. */
const LEAD = FEATURES.find((f) => f.title === `Ask ${SITE_NAME}`)!;

const byTitle = (title: string) => FEATURES.find((f) => f.title === title)!;

/**
 * The rest, under three outcomes (C-157 organize; the group titles are the only new words). Each
 * group's cards fill a two-column grid; the group of three ends on its widest card, which spans both
 * columns, so no group leaves a hole.
 */
export const FEATURE_GROUPS: { title: string; icon: LucideIcon; items: Feature[] }[] = [
  {
    title: "Manage every conversation",
    icon: Inbox,
    items: [byTitle("Team roles and assignment"), byTitle("Notifications, on your phone too")],
  },
  {
    title: "Automate the repetitive work",
    icon: Workflow,
    items: [byTitle("Scheduling, Reels and Stories"), byTitle("Sequences, and broadcasts soon")],
  },
  {
    title: "Understand and grow",
    icon: TrendingUp,
    items: [
      byTitle("Analytics and the weekly report"),
      byTitle("Comment intelligence"),
      byTitle("Product catalogue, orders and payment links"),
    ],
  },
];

/** One feature as a card; a feature with its own page is a whole-card link with a small arrow. */
function FeatureCard({ title, body, plan, note, href, icon }: Feature) {
  return (
    <li className={href ? "fcard is-link" : "fcard"}>
      <Ico icon={icon} />
      <h4>
        {href ? (
          <Link href={href as Route} className="fcard-link">
            {title}
          </Link>
        ) : (
          title
        )}
        {plan ? <span className="pl"> · {plan}</span> : null}
        {href ? <ArrowRight className="fcard-arrow size-4" aria-hidden /> : null}
      </h4>
      <p>{body}</p>
      {note ? <p className="note-line">{note}</p> : null}
    </li>
  );
}

/**
 * Everything else in the product, and what it connects to (C-155; C-157 merges Integrations in): Ask
 * Amplychat first and larger, the rest grouped under three outcomes, one "Go deeper" line, then the
 * connections with their honest status.
 */
export function Features() {
  return (
    <section className="sec sec-tight" id={SECTION_IDS.features} aria-labelledby="features-title">
      <div className="wrap">
        <h2 id="features-title" className="h2-sm">
          Everything your customer conversations need
        </h2>
        <p className="lede">From the first comment to the reply that closes the sale, in one place.</p>
        <div className="feat-lead after-head">
          <div className="feat-lead-h">
            <Ico icon={LEAD.icon} className="ico-ai" />
            <h3>{LEAD.title}</h3>
          </div>
          <div>
            <p>{LEAD.body}</p>
            {LEAD.note ? <p className="note-line">{LEAD.note}</p> : null}
          </div>
        </div>
        {FEATURE_GROUPS.map((group) => (
          <div key={group.title} className="fgroup">
            <h3>
              <Ico icon={group.icon} />
              {group.title}
            </h3>
            <ul className={group.items.length % 2 ? "fgrid odd" : "fgrid"}>
              {group.items.map((feature) => (
                <FeatureCard key={feature.title} {...feature} />
              ))}
            </ul>
          </div>
        ))}
        {/* "See every feature" leads to the /features hub (C-163, the SEO audit's link-equity finding). */}
        <p className="more-links">
          <Link href={FEATURES_PATH}>See every feature</Link>. Go deeper: <Link href="/features/ai-inbox">the AI inbox</Link>,{" "}
          <Link href="/features/comment-intelligence">comment intelligence</Link>,{" "}
          <Link href="/features/publishing">publishing</Link>, or <Link href="/compare">how {SITE_NAME} compares</Link>.
        </p>
        <Connections />
      </div>
    </section>
  );
}
