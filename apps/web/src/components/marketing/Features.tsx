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
import type { ReactNode } from "react";

import { SECTION_IDS } from "@/lib/marketing/site";

import { Container, SectionHeading } from "./primitives";

type Feature = { icon: LucideIcon; title: string; body: ReactNode; points?: string[]; note?: string };

// Every line here is in the product guide (knowledge/social-hood-product.md) and built.
const FEATURES: Feature[] = [
  {
    icon: Inbox,
    title: "One inbox for Instagram and WhatsApp",
    body: "Instagram DMs and WhatsApp chats arrive in one inbox in real time. Every new message is analysed for intent, sentiment and a lead score, so hot leads stand out.",
    points: ["Needs reply and Needs you views", "Sent, delivered and read status", "Shows when Instagram's 24-hour reply window closes"],
  },
  {
    icon: Sparkles,
    title: "AI replies, your way",
    body: "Choose an AI mode for each account. The AI understands and replies in English, Hindi and Hinglish.",
    points: [
      "Off: no AI replies",
      "Suggest: the AI drafts, you send, edit or dismiss",
      "Auto: the AI replies by itself when it's confident",
      "Unsure, upset or asking for a person? It goes to Needs you",
    ],
    note: "Auto is part of Pro.",
  },
  {
    icon: BookOpen,
    title: "Knowledge base and gaps",
    body: "Add prices, products, delivery, returns, timings and FAQs as text, a web page link, or a PDF, Word, TXT or Markdown file. Test a question to see how the AI would answer.",
    points: ["The AI only states facts from your knowledge", "Questions it couldn't answer show up as knowledge gaps"],
  },
  {
    icon: Zap,
    title: "Comment and DM automations",
    body: "Someone comments a keyword like LINK on a post or Reel, and they get the link in a private DM, with an optional public reply.",
    points: [
      "Tap first: a button before the link, which feels less spammy",
      "Follow nudge: a polite invite to follow, never a condition for getting the link",
      "DM keywords, with a preview before you turn it on",
    ],
  },
  {
    icon: MessageSquareText,
    title: "Comment management",
    body: "See what people say across your posts and Reels: sentiment, topics and a summary per post.",
    points: ["Reply publicly or send a private DM", "Flag spam and hide it automatically if you choose", "Hide, unhide or delete comments"],
  },
  {
    icon: CalendarClock,
    title: "Scheduling and publishing",
    body: "Schedule image posts, carousels and Reels on a calendar, or publish now. Drag posts to reschedule.",
    points: ["AI captions and hashtag suggestions", "A first comment posted right after", "A checklist that catches problems before publishing"],
  },
  {
    icon: BarChart3,
    title: "Analytics and the weekly digest",
    body: "Messages received, reply rate, first-response time, how many conversations the AI handled, sentiment and what customers asked about.",
    points: ["Post insights compared with your other posts", "A summary email every Monday at 9:00 AM your time"],
  },
  {
    icon: MessagesSquare,
    title: "Ask Social Hood",
    body: "Ask questions about your own business data in plain words. Answers show the numbers and time range they used, with links to the posts and conversations behind them.",
    points: [
      "Prepares a reply, a scheduled message or an automation draft for you to review",
      "Never sends, changes or deletes anything by itself",
    ],
  },
  {
    icon: Bell,
    title: "Notifications, on your phone too",
    body: "Alerts in the app, by email and as phone push notifications. Install Social Hood from your browser to hear when a conversation needs you or a new lead arrives.",
    points: ["You choose which alerts you get"],
  },
];

export function Features() {
  return (
    <section id={SECTION_IDS.features} aria-labelledby="features-title" className="scroll-mt-20 border-t border-line-subtle py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="features-title"
          eyebrow="Features"
          title="Everything your customer conversations need"
          intro="From the first comment to the reply that closes the sale, in one place."
        />
        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body, points, note }) => (
            <li key={title} className="flex flex-col rounded-2xl border border-line bg-panel p-6">
              <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand-fg">
                <Icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-base font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{body}</p>
              {points ? (
                <ul className="mt-4 space-y-2 text-sm">
                  {points.map((point) => (
                    <li key={point} className="flex gap-2">
                      <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-brand" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {note ? <p className="mt-4 text-xs text-brand-fg">{note}</p> : null}
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
