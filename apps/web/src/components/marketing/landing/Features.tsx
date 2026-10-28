import {
  BarChart3,
  Bell,
  CalendarClock,
  Globe,
  MessageSquareText,
  MessagesSquare,
  ShoppingBag,
  Timer,
  Users,
  type LucideIcon,
} from "lucide-react";

import { SECTION_IDS, SITE_NAME } from "@/lib/marketing/site";

type Feature = { icon: LucideIcon; title: string; body: string; plan?: string; note?: string };

// Every line is in the product guide and built, or says what it waits for (C-122, C-138). The inbox,
// the AI replies, knowledge gaps and the automations have their own sections above.
export const FEATURES: Feature[] = [
  {
    icon: CalendarClock,
    title: "Scheduling, Reels and Stories",
    body: "Posts, carousels, Reels and Stories on a calendar, with AI captions and hashtag ideas. Add Instagram collaborators to a post or Reel.",
  },
  {
    icon: MessageSquareText,
    title: "Comment intelligence",
    body: "Sentiment, topics and a summary for every post. Reply publicly or by DM, and hide spam automatically if you choose.",
  },
  {
    icon: MessagesSquare,
    title: `Ask ${SITE_NAME}`,
    body: "Ask about your own business data in plain words. Answers show the numbers and time range they used, with links to their sources. It prepares replies and drafts for you to review.",
    note: "Never sends, changes or deletes anything by itself",
  },
  {
    icon: BarChart3,
    title: "Analytics and the weekly report",
    body: "Messages received, reply rate, first-response time and what customers asked about, plus a summary email every Monday at 9:00 AM your time.",
  },
  {
    icon: ShoppingBag,
    title: "Product catalogue, orders and payment links",
    body: "Add products by hand or CSV, and the AI answers price and stock. Send a Razorpay link or a UPI request in the chat; the money goes to your own account.",
    plan: "Pro",
    note: "Shopify sync arrives with our Shopify app listing.",
  },
  {
    icon: Timer,
    title: "Sequences, and broadcasts soon",
    body: "Timed follow-ups after a lead is captured or a tag is added, stopping when they reply. WhatsApp broadcasts are coming soon, once consent rules are checked.",
  },
  {
    icon: Users,
    title: "Team roles and assignment",
    body: "Owners, admins and agents, with conversations assigned by hand or in turn. The Free plan has 1 seat, so a team starts on Pro.",
  },
  {
    icon: Globe,
    title: "A chat widget for your website",
    body: "The same inbox and AI answer visitors on your own site. It's on every plan, and Pro removes the small branding line.",
  },
  {
    icon: Bell,
    title: "Notifications, on your phone too",
    body: "In the app, by email and as phone push notifications when a conversation needs you or a lead arrives.",
  },
];

/** Everything else in the product, as a quiet three-column list on paper (C-155). */
export function Features() {
  return (
    <section className="sec" id={SECTION_IDS.features} aria-labelledby="features-title">
      <div className="wrap">
        <div className="split-head">
          <div>
            <p className="kicker">Features</p>
            <h2 id="features-title" className="h2">
              Everything your customer conversations need
            </h2>
          </div>
          <p className="lede">From the first comment to the reply that closes the sale, in one place.</p>
        </div>
        <ul className="more">
          {FEATURES.map(({ icon: Icon, title, body, plan, note }) => (
            <li key={title} className="mi">
              <div className="mi-h">
                <Icon className="size-5.5" strokeWidth={1.8} aria-hidden />
                <h3>{title}</h3>
                {plan ? <span className="pl">{plan}</span> : null}
              </div>
              <p>{body}</p>
              {note ? <p className="note-line">{note}</p> : null}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
