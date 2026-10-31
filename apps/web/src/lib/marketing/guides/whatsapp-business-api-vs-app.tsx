import { Server, Smartphone } from "lucide-react";
import Link from "next/link";

import { GuideH2, Pair, PairCard } from "@/components/marketing/guides/blocks";
import { Callout } from "@/components/site/Callout";

import { SITE_NAME } from "../site";
import { GUIDE_AUTHOR, type Guide } from "./types";

const N = SITE_NAME;

function Body() {
  return (
    <>
      <p>
        Many small businesses and creators already use WhatsApp for business, usually through the free WhatsApp Business
        app. Sooner or later someone tells you to “move to the API”. It sounds like an upgrade, but it is a different way of
        working, with different costs and rules. This guide explains what each one is, what changes when you switch, and how
        to tell which one you need right now.
      </p>

      <GuideH2>Two products with similar names</GuideH2>
      <Pair>
        <PairCard icon={Smartphone} mark="var(--wa)">
          <p>
            <strong>The WhatsApp Business app</strong> is the green app with the “B” on your phone. It is free, it runs on your
            phone (with a few linked devices such as WhatsApp Web), and it gives you a business profile, a catalogue, quick
            replies, labels, and greeting and away messages.
          </p>
        </PairCard>
        <PairCard icon={Server}>
          <p>
            <strong>The WhatsApp Business Platform</strong>, usually called the API, has no app of its own. Meta runs it, and you
            use it through software built on it, such as a team inbox or a CRM. It is built for more than one person replying,
            for automation, and for connecting WhatsApp to the rest of your tools.
          </p>
        </PairCard>
      </Pair>
      <Callout tone="means">
        <p>Neither is “better”. They suit different stages of a business.</p>
      </Callout>

      <GuideH2>What the app does well</GuideH2>
      <ul>
        <li>
          <strong>It costs nothing.</strong> Meta doesn&apos;t charge for messages sent from the app.
        </li>
        <li>
          <strong>It is quick to start.</strong> Install it, add your business details, and you are open.
        </li>
        <li>
          <strong>It covers the basics.</strong> Quick replies for common answers, an away message at night, labels to mark
          paid or pending orders, and a catalogue customers can browse.
        </li>
      </ul>
      <p>Where it starts to hurt:</p>
      <ul>
        <li>
          <strong>Sharing the work.</strong> The chats live on one account, so everyone who helps reply works from the same
          phone or its linked devices. There is no assigning a chat to a person, and no way to see who answered what.
        </li>
        <li>
          <strong>Volume.</strong> On a busy day, quick replies still mean a person typing or tapping every answer.
        </li>
        <li>
          <strong>Broadcast lists.</strong> They only reach people who have saved your number, which many customers never do.
        </li>
        <li>
          <strong>Everything else is separate.</strong> Instagram DMs, comments and orders sit in other apps.
        </li>
      </ul>

      <GuideH2>What changes with the API</GuideH2>
      <p>
        On the API, your WhatsApp number is connected to software instead of a phone. That opens up a team inbox, automatic
        replies, and links to the rest of your tools. It also brings rules the app doesn&apos;t have.
      </p>
      <h3>The 24-hour window and templates</h3>
      <p>
        When a customer messages you, a 24-hour window opens in which you can reply freely. Outside that window, or to start
        a conversation yourself, you can only send a <strong>template</strong>: a message you wrote in advance and Meta
        approved. Templates come in categories such as marketing, utility (order updates, for example) and authentication
        (one-time codes).
      </p>
      <h3>Meta&apos;s charges</h3>
      <p>
        Meta charges for template messages, per message, at a rate that depends on the category and the customer&apos;s
        country. Under Meta&apos;s current pricing, replies inside the 24-hour window are not charged. Rates change, so
        check{" "}
        <a href="https://developers.facebook.com/docs/whatsapp/pricing" rel="noopener noreferrer">
          Meta&apos;s WhatsApp pricing page
        </a>{" "}
        before you plan a campaign. The software you use usually charges its own fee on top; the two are separate.
      </p>
      <h3>Opt-in and quality</h3>
      <p>
        WhatsApp&apos;s business policy says you may only message people who have agreed to hear from you, and data
        protection laws in many countries ask for clear consent too. Meta also watches how customers react: if many people block or
        report your messages, your number&apos;s quality drops and Meta can limit how many people you can start conversations
        with in a day. New numbers start with a lower limit that rises as you build a good record.
      </p>
      <h3>Your number</h3>
      <p>
        A number connected to the API is used through that software rather than the regular app. Meta has started letting
        some businesses keep the Business app on a number that is also connected to the API, with limits, so the rules are
        changing. Before you move the number your customers already know, check Meta&apos;s current guidance, or ask your
        provider exactly what happens to your chat history.
      </p>

      <GuideH2>How to choose</GuideH2>
      <Pair>
        <PairCard icon={Smartphone} mark="var(--wa)">
          <p>The app is probably enough if:</p>
          <ul>
            <li>one or two people handle all the chats,</li>
            <li>you can answer most messages within a few hours by hand,</li>
            <li>you rarely message customers who haven&apos;t written to you first.</li>
          </ul>
        </PairCard>
        <PairCard icon={Server}>
          <p>The API starts to make sense when:</p>
          <ul>
            <li>several people reply and you need to know who handles which chat,</li>
            <li>the same questions arrive all day and you want them answered in minutes, at night too,</li>
            <li>you sell on Instagram as well and want one inbox instead of two phones,</li>
            <li>you want order updates or reminders sent as proper templates rather than typed by hand.</li>
          </ul>
        </PairCard>
      </Pair>
      <Callout tone="tip" title="A practical middle path">
        <p>
          Keep the app on your personal selling number while it works, and put the API on a number
          you are happy to run through software. Watch which one your customers use.
        </p>
      </Callout>

      <GuideH2>{`Where ${N} fits`}</GuideH2>
      <p>
        {N} is built on Meta&apos;s official APIs. You connect a WhatsApp number through Meta&apos;s own sign-up window, and
        its chats arrive in the same inbox as your Instagram DMs. What that gives you today:
      </p>
      <ul>
        <li>
          <strong>AI replies from your knowledge</strong>, as drafts you send (Suggest) or
          sent by themselves when the AI is confident (Auto, on Pro). Anything about refunds, complaints or that the AI
          isn&apos;t sure of goes to a person.
        </li>
        <li>
          <strong>Templates from the inbox</strong> when a conversation&apos;s 24-hour window has closed, using the templates
          Meta approved for your account.
        </li>
        <li>
          <strong>Teamwork</strong>: assign chats, saved replies, business hours and away messages.
        </li>
        <li>
          <strong>Payment requests in the chat</strong> on Pro and Max: a Razorpay link paid to your own Razorpay account,
          or your UPI ID marked paid by hand. The money goes to you, never through us.
        </li>
      </ul>
      <Callout tone="note" title="What to know before you decide">
        <ul>
          <li>
            Meta bills WhatsApp messaging fees to your business directly. {N}&apos;s plans don&apos;t include them and add
            nothing on top.
          </li>
          <li>
            Marketing broadcasts are built but not switched on yet: they open once our review of consent rules is done.
          </li>
          <li>
            Product messages from your WhatsApp catalogue need your own Meta catalogue and Meta&apos;s approval.
          </li>
          <li>Connecting WhatsApp depends on Meta&apos;s approval of {N}&apos;s app.</li>
        </ul>
      </Callout>
      <p>
        The <Link href="/features/ai-inbox">AI inbox page</Link> shows how replies work, the{" "}
        <Link href="/compare/interakt">comparison with Interakt</Link> sets {N} beside a popular WhatsApp-first tool,
        and the <Link href="/pricing">pricing page</Link> lists every plan&apos;s limits.
      </p>
    </>
  );
}

export const WHATSAPP_API_VS_APP: Guide = {
  slug: "whatsapp-business-api-vs-app",
  title: "WhatsApp Business API vs app for small business",
  description:
    "The WhatsApp Business app and the API compared for small businesses and creators: costs, templates, the 24-hour window, teams, and when to switch.",
  h1: "WhatsApp Business API vs the WhatsApp Business app: what small businesses need",
  published: "2026-10-28",
  updated: "2026-10-29",
  readingMinutes: 5,
  author: GUIDE_AUTHOR,
  tags: ["WhatsApp"],
  sections: [
    "Two products with similar names",
    "What the app does well",
    "What changes with the API",
    "How to choose",
    `Where ${N} fits`,
  ],
  faq: [
    {
      question: "Is the WhatsApp Business API free?",
      answer:
        "Meta charges for template messages, per message, by category and country. Under Meta's current pricing, replies inside the 24-hour customer service window are not charged. The software you use the API through usually has its own fee.",
    },
    {
      question: "Can I message customers who haven't written to me on the API?",
      answer:
        "Only with a template Meta has approved, and only if they have agreed to hear from you. Free-form replies are allowed within 24 hours of the customer's last message.",
    },
  ],
  related: [
    { label: "WhatsApp auto-reply in Amplychat", href: "/whatsapp/auto-reply" },
    { label: "The AI inbox", href: "/features/ai-inbox" },
    // C-163: the matching audience page beside the comparison (the SEO audit's internal-linking finding).
    { label: `${N} for businesses`, href: "/for-businesses" },
    { label: `${N} vs Interakt`, href: "/compare/interakt" },
    // C-163 (gloss)
    { label: "WhatsApp terms explained", href: "/glossary" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  Body,
};
