import {
  BarChart3,
  Bell,
  BookOpen,
  CalendarClock,
  Globe,
  Inbox,
  MessageSquareText,
  MessagesSquare,
  ShoppingBag,
  Sparkles,
  Timer,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { CSSProperties } from "react";

import { SECTION_IDS, SITE_NAME } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { BentoGrid, BentoGridItem } from "./effects/bento-grid";
import { Illustration, type IllustrationName } from "./illustrations/Illustrations";
import { Container, MARKETING_CARD_GLASS, MARKETING_CARD_HOVER, SectionHeading } from "./primitives";

type Feature = {
  icon: LucideIcon;
  title: string;
  body: string;
  illustration: IllustrationName;
  /** Bento layout: how many of the grid's columns the card takes (the grid has 2, then 6). */
  span: string;
  note?: string;
};

// Every line is in the product guide and built, or says what it waits for (C-122, C-138). The
// first six are the core; the last four are what was added after launch.
const FEATURES: Feature[] = [
  {
    icon: Sparkles,
    title: "AI replies from your own knowledge",
    body: "Choose Off, Suggest or Auto for each account. The AI drafts or sends replies using only what's in your knowledge base, in English, Hindi and Hinglish. When it isn't sure, it hands over and records the gap.",
    illustration: "draft",
    span: "md:col-span-2 lg:col-span-4",
    note: "Auto is part of Pro.",
  },
  {
    icon: Inbox,
    title: "One inbox, with a hand-off",
    body: "Instagram DMs and WhatsApp chats arrive in real time, tagged with intent, sentiment and a lead score. Unsure, upset or asking for a person? It goes to Needs you.",
    illustration: "inbox",
    span: "lg:col-span-2",
  },
  {
    icon: Zap,
    title: "Comment and DM automations",
    body: "Someone comments a keyword like LINK on a post or Reel and gets the link in a private DM, with an optional public reply. DM keywords work too, with a preview before you turn them on.",
    illustration: "automation",
    span: "md:col-span-2 lg:col-span-3",
  },
  {
    icon: MessageSquareText,
    title: "Comment intelligence",
    body: "Sentiment, topics and a summary for every post. Reply publicly or by DM, and hide spam automatically if you choose.",
    illustration: "comments",
    span: "md:col-span-2 lg:col-span-3",
  },
  {
    icon: CalendarClock,
    title: "Scheduling, Reels and Stories",
    body: "Posts, carousels, Reels and Stories on a calendar, with AI captions and hashtag ideas. Add Instagram collaborators to a post or Reel.",
    illustration: "schedule",
    span: "lg:col-span-2",
  },
  {
    icon: MessagesSquare,
    title: `Ask ${SITE_NAME}`,
    body: "Ask about your own business data in plain words. Answers show the numbers and time range they used, with links to their sources. It prepares replies and drafts for you to review.",
    illustration: "ask",
    span: "lg:col-span-2",
    note: "Never sends, changes or deletes anything by itself",
  },
  {
    icon: BarChart3,
    title: "Analytics and the weekly report",
    body: "Messages received, reply rate, first-response time and what customers asked about, plus a summary email every Monday at 9:00 AM your time.",
    illustration: "analytics",
    span: "md:col-span-2 lg:col-span-2",
  },
  {
    icon: ShoppingBag,
    title: "Product catalogue, orders and payment links",
    body: "Add products by hand or CSV, and the AI answers price and stock. Send a Razorpay link or a UPI request in the chat; the money goes to your own account. Part of Pro.",
    illustration: "orders",
    span: "lg:col-span-2",
    note: "Shopify sync arrives with our Shopify app listing.",
  },
  {
    icon: Timer,
    title: "Sequences, and broadcasts soon",
    body: "Timed follow-ups after a lead is captured or a tag is added, stopping when they reply. WhatsApp broadcasts are coming soon, once India's consent rules are checked.",
    illustration: "sequence",
    span: "lg:col-span-2",
  },
  {
    icon: Users,
    title: "Team roles and assignment",
    body: "Owners, admins and agents, with conversations assigned by hand or in turn. The Free plan has 1 seat, so a team starts on Pro.",
    illustration: "team",
    span: "md:col-span-2 lg:col-span-2",
  },
];

const MORE: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: BookOpen,
    title: "Knowledge gaps",
    body: "When the answer isn't in your knowledge, the AI doesn't guess. It hands the conversation to you and records the question, so you know what to add.",
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

export function Features() {
  return (
    <section id={SECTION_IDS.features} aria-labelledby="features-title" className="scroll-mt-24 py-16 sm:py-20">
      <Container>
        <SectionHeading
          id="features-title"
          eyebrow="Features"
          title="Everything your customer conversations need"
          intro="From the first comment to the reply that closes the sale, in one place."
        />
        <BentoGrid className="mt-12" label="Features">
          {FEATURES.map((feature, index) => (
            <BentoGridItem
              key={feature.title}
              index={index}
              className={feature.span}
              title={feature.title}
              description={feature.body}
              note={feature.note}
              icon={
                <span className="grid size-7 place-items-center rounded-lg bg-brand-soft text-brand-fg">
                  <feature.icon className="size-4" aria-hidden />
                </span>
              }
              header={<Illustration name={feature.illustration} className="h-auto min-h-56 flex-1" />}
            />
          ))}
        </BentoGrid>
        <p className="mt-4 text-center text-xs text-fg-secondary">Illustrations with example data.</p>

        <ul className="mx-auto mt-8 grid max-w-6xl gap-4 md:grid-cols-3" aria-label="Also in the product">
          {MORE.map(({ icon: Icon, title, body }, index) => (
            <li key={title} data-reveal style={{ "--reveal-delay": `${index * 80}ms` } as CSSProperties}>
              <div className={cn(MARKETING_CARD_GLASS, MARKETING_CARD_HOVER, "flex h-full gap-3 p-4")}>
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-fg">
                  <Icon className="size-4" aria-hidden />
                </span>
                <div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-fg-secondary">{body}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
