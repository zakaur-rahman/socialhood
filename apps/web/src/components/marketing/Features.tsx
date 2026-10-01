import {
  BarChart3,
  Bell,
  BookOpen,
  CalendarClock,
  Inbox,
  MessageSquareText,
  MessagesSquare,
  Sparkles,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { CSSProperties } from "react";

import { SECTION_IDS } from "@/lib/marketing/site";

import { BentoGrid, BentoGridItem } from "./effects/bento-grid";
import { LazyIllustration, type IllustrationName } from "./illustrations/LazyIllustration";
import { Container, SectionHeading } from "./primitives";

type Feature = {
  icon: LucideIcon;
  title: string;
  body: string;
  illustration: IllustrationName;
  /** Bento layout: two of the three columns on wide screens. */
  wide?: boolean;
  note?: string;
};

// Every line is in the product guide (knowledge/social-hood-product.md) and built.
const FEATURES: Feature[] = [
  {
    icon: Sparkles,
    title: "AI replies from your own knowledge",
    body: "Choose Off, Suggest or Auto for each account. The AI drafts or sends replies using only what's in your knowledge base, in English, Hindi and Hinglish.",
    illustration: "draft",
    wide: true,
    note: "Auto is part of Pro.",
  },
  {
    icon: Inbox,
    title: "One inbox, with a hand-off",
    body: "Instagram DMs and WhatsApp chats arrive in real time, tagged with intent, sentiment and a lead score. Unsure, upset or asking for a person? It goes to Needs you.",
    illustration: "inbox",
  },
  {
    icon: BookOpen,
    title: "Knowledge gaps",
    body: "When the answer isn't in your knowledge, the AI doesn't guess. It hands the conversation to you and records the question, so you know what to add.",
    illustration: "gaps",
  },
  {
    icon: Zap,
    title: "Comment and DM automations",
    body: "Someone comments a keyword like LINK on a post or Reel and gets the link in a private DM, with an optional public reply. DM keywords work too, with a preview before you turn them on.",
    illustration: "automation",
    wide: true,
  },
  {
    icon: BarChart3,
    title: "Analytics and the weekly digest",
    body: "Messages received, reply rate, first-response time, the conversations the AI handled and what customers asked about, plus a summary email every Monday at 9:00 AM your time.",
    illustration: "analytics",
    wide: true,
  },
  {
    icon: MessagesSquare,
    title: "Ask Social Hood",
    body: "Ask about your own business data in plain words. Answers show the numbers and time range they used, with links to their sources. It prepares replies and drafts for you to review.",
    illustration: "ask",
    note: "Never sends, changes or deletes anything by itself",
  },
];

const MORE: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: MessageSquareText,
    title: "Comment management",
    body: "Sentiment, topics and a summary per post. Reply publicly or by DM, and hide spam automatically if you choose.",
  },
  {
    icon: CalendarClock,
    title: "Scheduling and publishing",
    body: "Posts, carousels and Reels on a calendar, with AI captions, hashtag ideas and a first comment.",
  },
  {
    icon: Bell,
    title: "Notifications, on your phone too",
    body: "In the app, by email and as phone push notifications when a conversation needs you or a lead arrives.",
  },
];

export function Features() {
  return (
    <section id={SECTION_IDS.features} aria-labelledby="features-title" className="scroll-mt-24 py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="features-title"
          eyebrow="Features"
          title="Everything your customer conversations need"
          intro="From the first comment to the reply that closes the sale, in one place."
        />
        <BentoGrid className="mt-14" label="Features">
          {FEATURES.map((feature, index) => (
            <BentoGridItem
              key={feature.title}
              index={index}
              className={feature.wide ? "md:col-span-2" : undefined}
              title={feature.title}
              description={feature.body}
              note={feature.note}
              icon={
                <span className="grid size-7 place-items-center rounded-lg bg-brand-soft text-brand-fg">
                  <feature.icon className="size-4" aria-hidden />
                </span>
              }
              header={<LazyIllustration name={feature.illustration} className="h-auto min-h-56 flex-1" />}
            />
          ))}
        </BentoGrid>
        <p className="mt-4 text-center text-xs text-fg-secondary">Illustrations with example data.</p>

        <ul className="mx-auto mt-10 grid max-w-6xl gap-4 md:grid-cols-3" aria-label="Also in Social Hood">
          {MORE.map(({ icon: Icon, title, body }, index) => (
            <li key={title} data-reveal style={{ "--reveal-delay": `${index * 80}ms` } as CSSProperties}>
              <div className="flex h-full gap-3 rounded-2xl border border-line bg-panel/60 p-4 transition-colors duration-200 hover:border-line-strong">
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
