import { FileText, MessageCircle } from "lucide-react";
import Link from "next/link";

import { Checklist, GuideH2, Pair, PairCard } from "@/components/marketing/guides/blocks";
import { Callout } from "@/components/site/Callout";

import { SITE_NAME } from "../site";
import { GUIDE_AUTHOR, type Guide } from "./types";

const N = SITE_NAME;

function Body() {
  return (
    <>
      <p>
        If you sell on Instagram, your DMs are your shop counter. Someone asks the price of a denim jacket at 11 at night, someone
        else wants to know if you deliver to their city, a third person just sends “details?” under a Reel. Answering all of it
        by hand works until the day a post takes off. Then the questions pile up, replies go out hours late, and some people
        buy from whoever answered first.
      </p>
      <p>
        Auto-replies fix the speed problem, but a bad one creates a new problem: the customer can tell. A stiff, generic
        message that ignores what they asked feels like talking to a wall, and that is worse than a slow human reply. This
        guide is about getting the speed without that feeling.
      </p>

      <GuideH2>Why most auto-replies feel robotic</GuideH2>
      <p>Most automatic DMs sound like a bot for a handful of reasons, and each one has a fix:</p>
      <ul>
        <li>
          <strong>They answer a question nobody asked.</strong> “Thanks for reaching out! Our team will get back to you soon”
          in reply to “Is the black one in M?” tells the customer you didn&apos;t read the message.
        </li>
        <li>
          <strong>They are too long.</strong> A DM is a chat, not an email. Three short sentences beat a paragraph with a
          menu of options.
        </li>
        <li>
          <strong>They use a voice that isn&apos;t yours.</strong> If your captions are warm and casual, a reply that opens
          with “Dear valued customer” sounds like someone else.
        </li>
        <li>
          <strong>They guess.</strong> The fastest way to lose trust is a confident reply with the wrong price or a delivery
          promise you can&apos;t keep.
        </li>
      </ul>

      <GuideH2>Start with the questions you actually get</GuideH2>
      <p>
        Before you automate anything, scroll back through your last few weeks of DMs and note the questions that come up
        again and again. For most small businesses the list is short: price, sizes and colours, stock, delivery areas and time,
        cash on delivery, returns and exchanges, and how to order. Write each one down with the answer you would give.
      </p>
      <p>
        This list is the raw material for good automatic replies. A reply can only be as good as the facts behind it. If
        your return policy lives only in your head, no tool can answer a return question well.
      </p>

      <GuideH2>{"Write answers the way you'd say them"}</GuideH2>
      <p>
        When you write the answers, write them the way you would type them to a customer, not the way a policy document
        reads. Compare:
      </p>
      <Pair>
        <PairCard icon={FileText}>
          <p>“Returns are accepted within seven (7) days of delivery subject to the conditions mentioned.”</p>
        </PairCard>
        <PairCard icon={MessageCircle} mark="var(--ig)">
          <p>“Yes, you can return or exchange it within 7 days of delivery, as long as the tags are on.”</p>
        </PairCard>
      </Pair>
      <p>
        The second one is the same fact in your voice. It also answers the real question (“can I return it?”) in the first
        word. Keep that pattern: answer first, detail second, and an easy next step at the end, such as offering the order
        link.
      </p>
      <p>
        Decide a few voice rules too: whether you use emoji, how formal you are, words you always or never use, and whether
        you sign off with a name. In {N} these live in the brand voice settings next to your knowledge, and every AI draft
        follows them.
      </p>

      <GuideH2>Answer from your facts, never from a guess</GuideH2>
      <p>
        The difference between a useful AI reply and a dangerous one is where the facts come from. A general chatbot will
        happily invent a delivery time that sounds right. For a business, that is a problem you pay for later in refunds and
        angry comments.
      </p>
      <p>
        {N}&apos;s AI drafts replies only from what you add to your knowledge (documents, questions and answers, and your
        product catalogue) and the conversation itself. When the answer isn&apos;t there, it doesn&apos;t make one up: the
        conversation goes to you, and the question is recorded as a knowledge gap so you can add the answer once and have it
        covered next time. Over a few weeks, the gaps list turns into a map of what your customers really want to know.
      </p>

      <GuideH2>Decide what never gets an automatic answer</GuideH2>
      <p>
        Some messages should always reach a person, however good the AI is. Make that list before you turn anything on:
      </p>
      <ul>
        <li>refund requests and payment problems,</li>
        <li>complaints and angry customers,</li>
        <li>legal threats or anything about safety,</li>
        <li>abuse,</li>
        <li>anything the AI isn&apos;t confident about.</li>
      </ul>
      <p>
        In {N}, these go to a “Needs you” view instead of getting an automatic reply, and you can add your own phrases that
        should always reach a person. When you reply yourself, the AI steps back in that conversation, so the customer
        never gets a human message followed by a bot one.
      </p>

      <GuideH2>{"Stay inside Instagram's rules"}</GuideH2>
      <p>A few Instagram rules shape every DM tool, and knowing them saves confusion:</p>
      <ul>
        <li>
          <strong>Business tools need a professional account.</strong> A Business or Creator account works; a personal one
          doesn&apos;t. Switching is free in the Instagram app.
        </li>
        <li>
          <strong>The 24-hour window.</strong> A business can message a customer within 24 hours of that customer&apos;s last
          message. After that, you wait until they write again. {N} shows when the window for a conversation closes, so you
          know which chats to answer first.
        </li>
        <li>
          <strong>No forced follows.</strong> You can invite someone to follow you, but you can&apos;t make a follow the
          price of getting an answer.
        </li>
      </ul>

      <GuideH2>Start with suggestions, then let it send</GuideH2>
      <p>
        You don&apos;t have to trust the AI on day one. {N} has three modes for each connected account. <strong>Off</strong>{" "}
        means no AI replies. <strong>Suggest</strong> writes a draft above the reply box for you to send, edit or redo.{" "}
        <strong>Auto</strong> sends a reply by itself when it is confident and still hands the rest to you; Auto is part of
        the Pro plan.
      </p>
      <Callout tone="tip">
        <p>
          A sensible path is a week or two on Suggest. Read every draft before it goes. Each time you edit one, ask why: a
          missing fact means a knowledge gap to fill, a wrong tone means a voice rule to change. Once you find yourself sending
          most drafts unchanged, Auto is a small step rather than a leap. Even then, look through the conversations it handled
          now and then.
        </p>
      </Callout>

      <GuideH2>A short checklist</GuideH2>
      <Checklist>
        <li>List the ten questions you get most, with the answers you would type.</li>
        <li>Add them to your knowledge, along with your products, prices and policies.</li>
        <li>Set your voice: tone, emoji, words to use and avoid.</li>
        <li>Decide what always goes to a person.</li>
        <li>Run on Suggest, fix the gaps it finds, then consider Auto.</li>
      </Checklist>
      <p>
        If you want to see how the inbox, the drafts and the hand-off fit together, the{" "}
        <Link href="/features/ai-inbox">AI inbox page</Link> walks through it, and the{" "}
        <Link href="/pricing">pricing page</Link> lists what each plan includes. Instagram and WhatsApp connections depend
        on Meta&apos;s approval of {N}&apos;s app.
      </p>
    </>
  );
}

export const INSTAGRAM_DM_AUTO_REPLIES: Guide = {
  slug: "instagram-dm-auto-replies",
  title: "Instagram DM auto-replies without the bot feel",
  description:
    "Auto-reply to Instagram DMs in your own voice: answer from your facts, never guess, and hand the hard messages to a person.",
  h1: "How to auto-reply to Instagram DMs without sounding like a bot",
  published: "2026-10-28",
  updated: "2026-10-29",
  readingMinutes: 5,
  author: GUIDE_AUTHOR,
  tags: ["Instagram", "AI replies"],
  sections: [
    "Why most auto-replies feel robotic",
    "Start with the questions you actually get",
    "Write answers the way you'd say them",
    "Answer from your facts, never from a guess",
    "Decide what never gets an automatic answer",
    "Stay inside Instagram's rules",
    "Start with suggestions, then let it send",
    "A short checklist",
  ],
  hero: "aiDraft",
  faq: [
    {
      question: "Can I auto-reply to Instagram DMs from a personal account?",
      answer:
        "No. Instagram only allows business tools on professional (Business or Creator) accounts. Switching is free in the Instagram app's settings.",
    },
    {
      question: "Can I reply to a customer who messaged me last week?",
      answer:
        "Not until they write again. Instagram lets a business message a customer within 24 hours of the customer's last message.",
    },
    {
      question: "Will an AI reply make up prices or delivery times?",
      answer: `${N}'s AI answers only from the knowledge you add and the conversation. When the answer isn't there, it hands the conversation to you and records the question as a knowledge gap.`,
    },
  ],
  related: [
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: "Comment-to-DM automations", href: "/guides/comment-to-dm-automations" },
    // C-163: the matching audience page and one comparison (the SEO audit's internal-linking finding).
    { label: `${N} for businesses`, href: "/for-businesses" },
    { label: `${N} vs InstantDM`, href: "/compare/instantdm" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  Body,
};
