/**
 * The automation and channel pages (C-163, the SEO audit's programmatic set 1): one entry per page,
 * rendered by components/marketing/automations/AutomationPageView. Each answers one search ("how to
 * auto-reply to Instagram comments with a DM" and so on) with what the feature is, how it works in
 * Amplychat (the real triggers, match modes and limits), the Meta rules that apply, a set-up
 * walkthrough, plan limits and AI credits, a labelled example, mistakes to avoid and a few questions
 * of its own.
 *
 * Truth: every product line is checked against the code named beside it; limits are read from
 * plan-table.json (billing/plans.py ENTITLEMENTS), never typed; credit costs are billing/plans.py
 * CREDIT_COSTS. Every Meta rule cites Meta's own page in `META` with the date it was read.
 */
import { AtSign, Equal, Hand, Heart, KeyRound, ListChecks, type LucideIcon, MapPin, MessageCircle, MessagesSquare, PanelsTopLeft, Reply, Send, WholeWord, Asterisk } from "lucide-react";
import type { ComponentType } from "react";

import { ExampleThread } from "@/components/marketing/automations/blocks";
import { has, type Limit } from "@/components/marketing/explainers/content";
import { Checklist, GuideH2, StepCards } from "@/components/marketing/guides/blocks";
import { META_WHATSAPP_PRICING_URL } from "@/components/marketing/WhatsAppCharges";
import { Callout } from "@/components/site/Callout";

import type { GuideFaq } from "./guides/types";
import table from "./plan-table.json";
import { SITE_NAME } from "./site";

const N = SITE_NAME;
const E = table.entitlements;

/** The hub: every automation type, by channel. */
export const AUTOMATIONS_PATH = "/automations";

export type AutomationChannel = "instagram" | "whatsapp" | "web";

export const CHANNEL_NAME: Record<AutomationChannel, string> = { instagram: "Instagram", whatsapp: "WhatsApp", web: "Website chat" };

/** The product scene under a page's head: a landing scene where one fits, a small card scene otherwise. */
export type AutomationScene = "comments" | "story" | "keywords" | "starters" | "modes" | "widget";

/** A Meta page a rule comes from, with the day we read it. */
export type MetaSource = { label: string; url: string; read: string };

/**
 * Meta's own pages behind every rule these pages state. All read on 2026-10-31 with an automated
 * fetch, except `limits`, whose figures were confirmed through a web search and a second fetch of
 * the same page (the first summary left them out).
 */
export const META = {
  // "within 7 days of the creation time of the comment"; "Only one message can be sent to the
  // commenter"; follow-ups "only if the recipient responds, and must be sent within 24 hours".
  privateReplies: {
    label: "Private replies, Instagram Platform",
    url: "https://developers.facebook.com/docs/instagram-platform/private-replies",
    read: "2026-10-31",
  },
  // The standard messaging window: "For most user actions, it lasts 24 hours"; the separate 7-day
  // Human Agent window; conversations begin from "posts, story mentions, and other channels".
  messaging: {
    label: "Send messages, Instagram API with Instagram Login",
    url: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api",
    read: "2026-10-31",
  },
  // "750 calls per hour per Instagram professional account for private replies to comments";
  // "100 calls per second per Instagram professional account for messages that contain text".
  limits: {
    label: "Instagram Platform overview: rate limits",
    url: "https://developers.facebook.com/docs/instagram-platform/overview",
    read: "2026-10-31",
  },
  // "A maximum of 4 questions can be set via the Ice Breaker API"; "currently not available on desktop".
  iceBreakers: {
    label: "Ice breakers, Instagram Messaging API",
    url: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/ice-breakers",
    read: "2026-10-31",
  },
  // "automated chat experiences must disclose that a person is interacting with an automated service".
  policy: {
    label: "Messenger Platform and Instagram Messaging API policy",
    url: "https://developers.facebook.com/documentation/business-messaging/messenger-platform/policy",
    read: "2026-10-31",
  },
  // "When a WhatsApp user messages you or calls you, a 24-hour timer called a customer service window
  // starts"; it resets when they write again; "When the window closes, you can only send pre-approved
  // template messages."
  waWindow: {
    label: "Send messages: customer service windows, WhatsApp Cloud API",
    url: "https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages",
    read: "2026-10-31",
  },
  // Templates charged per delivered message by category and market; "one free tier of 1,000 delivered
  // service messages per month" per number, charged from the 1,001st, as of October 1, 2026.
  waPricing: { label: "Pricing on the WhatsApp Business Platform", url: META_WHATSAPP_PRICING_URL, read: "2026-10-31" },
} as const satisfies Record<string, MetaSource>;

export type AutomationLink = { label: string; href: string };

export type AutomationPage = {
  path: string;
  channel: AutomationChannel;
  /** The short name: the hub's card, the breadcrumb, the footer of related links. */
  name: string;
  /** The title tag, at most 48 characters, so "{title} · Amplychat" stays within 60. */
  title: string;
  /** The meta description and the hub card's line: 50 to 155 characters. */
  description: string;
  h1: string;
  lede: string;
  /** The searches the page answers (for the report and llms.txt; not rendered). */
  queries: readonly string[];
  icon: LucideIcon;
  scene: AutomationScene;
  published: string;
  updated: string;
  /** The body's h2s in order (each a `GuideH2` with this text); the contents read them. */
  sections: readonly string[];
  Body: ComponentType;
  /** Plan limits that matter here, from plan-table.json. */
  limits: Limit[];
  /** What uses AI credits here (CREDIT_COSTS), as sentences. */
  credits: readonly string[];
  /** Three or four questions no other page asks (FAQPage on this page only). */
  faq: GuideFaq[];
  sources: readonly MetaSource[];
  /** The matching guide, and the matching audience page. */
  guide: AutomationLink;
  audience: AutomationLink;
  /** One or two more pages worth reading next. */
  related: AutomationLink[];
};

const fmt = (v: number | boolean | null) => has(v);
/** A plan limit row from plan-table.json, worded as the pricing page words it. */
function planRow(label: string, key: keyof typeof E, format: (v: number | boolean | null) => string = fmt): Limit {
  const values = E[key] as unknown as Record<"free" | "pro" | "max", number | boolean | null>;
  return { label, free: format(values.free), pro: format(values.pro), max: format(values.max) };
}
const modes = (v: number | boolean | null) => ((v as unknown as string[]).includes("auto") ? "Off, Suggest, Auto" : "Off, Suggest");

// billing/plans.py CREDIT_COSTS. A message you write is sent without the AI, so it uses none.
const CREDIT_FIXED = "Sending a message you wrote uses no AI credits.";
const CREDIT_READ = "The AI reads each incoming message for its intent and sentiment, which uses one credit, as everywhere in the inbox.";
const CREDIT_AUTOMATION_AI = "An AI reply inside an automation uses two credits, and is part of Pro and Max.";
const CREDIT_DRAFT = "A draft (Suggest) or an automatic reply (Auto) uses two credits.";

const ROW_AUTOMATIONS = planRow("Active automations", "active_automations");
const ROW_AI_AUTOMATIONS = planRow("AI replies in automations", "ai_reply_automations");
const ROW_STEPS = planRow("Steps in a flow", "flow_steps");
const ROW_MODES = planRow("AI modes", "ai_modes", modes);
const ROW_CREDITS = planRow("AI credits a month", "ai_credits_monthly");

const GUIDE_COMMENTS = { label: "The comment-to-DM guide: keywords and messages that work", href: "/guides/comment-to-dm-automations" };
const GUIDE_DMS = { label: "How to auto-reply to Instagram DMs without sounding like a bot", href: "/guides/instagram-dm-auto-replies" };
const GUIDE_WHATSAPP = { label: "WhatsApp Business API vs the app", href: "/guides/whatsapp-business-api-vs-app" };
const FOR_CREATORS = { label: "Amplychat for creators", href: "/for-creators" };
const FOR_BUSINESSES = { label: "Amplychat for businesses", href: "/for-businesses" };
const SAFETY = { label: "How sending stays within Meta's limits", href: "/safety" };

// ---------------------------------------------------------------- Instagram: comment to DM

function CommentToDmBody() {
  return (
    <>
      <p>
        Comment to DM is the automation behind every “comment LINK and I&apos;ll send it to you” post. Someone comments your keyword
        under a post or Reel, gets a short public reply if you want one, and receives a direct message with what they asked for.
        The post collects comments, and every interested person lands in your inbox, where the conversation can carry on.
      </p>

      <GuideH2>How it works in Amplychat</GuideH2>
      <p>An automation has four parts, and each one is a setting in the editor:</p>
      <StepCards
        items={[
          // models/automations.py PostScope and CommentSurface; Live comments wait on Meta's approval.
          { icon: MapPin, body: <><strong>Where it listens</strong>: one or a few chosen posts, all posts, or the next post you publish.</> },
          // Trigger comment_keyword and comment_any (any comment needs chosen posts or the next post).
          { icon: KeyRound, body: <><strong>What starts it</strong>: one of your keywords, or any comment on the posts you choose.</> },
          // public_reply_texts: up to five, one picked at random; at most 300 characters each.
          { icon: MessagesSquare, body: <><strong>The public reply</strong>: up to five versions, one picked at random, so the thread doesn&apos;t look automated.</> },
          // confirm_first (FR-AUT-21): an opening with one button; the message follows their tap or reply.
          { icon: Send, body: <><strong>The DM</strong>: your message with up to three link buttons, or a short opening with a button and the link after their tap.</> },
        ]}
      />
      <p>
        Keywords match as a <strong>whole word</strong> by default, so “price?” and “What&apos;s the PRICE” both count but “priceless”
        doesn&apos;t. You can also choose an <strong>exact message</strong>, or a keyword the comment merely <strong>contains</strong>. Case,
        accents and extra spaces are ignored, and words in any script count. A reply inside a comment thread starts keyword
        automations only; “any comment” answers top-level comments.
      </p>
      <p>
        You can also keep an automation to business hours or outside them, give it a start and end date, invite people who
        don&apos;t follow you to follow after the link, or build a longer flow with questions, branches and delays.
      </p>

      <GuideH2>{"Meta's rules for replying to comments"}</GuideH2>
      <Callout tone="note" title="The private-reply rule">
        <p>
          Instagram lets a business answer a comment with <strong>one private message</strong>, sent{" "}
          <strong>within 7 days</strong> of the comment. More messages can follow only if the person replies, and then within 24
          hours of their reply.
        </p>
      </Callout>
      <ul>
        <li>
          <strong>Rate limit.</strong> Meta allows 750 private replies an hour for each Instagram professional account. {N} queues
          the rest and sends them as the limit allows, and drops any that would go out after the 7 days.
        </li>
        <li>
          <strong>Tap first</strong> fits the rule: the tap is a reply, so the link that follows is allowed and expected.
        </li>
        <li>
          <strong>No follow-gating.</strong> The follow invitation comes after the link and never holds it back.
        </li>
        <li>
          <strong>Say it&apos;s automated.</strong> Meta asks automated chats to say so; add a short disclosure line in your workspace
          settings and {N} puts it on automated messages.
        </li>
      </ul>

      <GuideH2>Set it up</GuideH2>
      <Checklist>
        <li>Connect your Instagram Business or Creator account with Instagram&apos;s own login.</li>
        <li>Open Automations, create one and choose “Instagram comment keyword” or “Any Instagram comment”.</li>
        <li>Pick the post or Reel, all posts, or your next post, and add your keywords.</li>
        <li>Write two to five public replies, then the DM. Turn on tap first if the DM carries a link.</li>
        <li>Preview it and switch it on. Each send shows on the automation&apos;s activity, with the reason if one fails.</li>
      </Checklist>

      <GuideH2>An example</GuideH2>
      <ExampleThread
        title="A Reel with a gear list"
        setting="A made-up creator posts a studio tour and asks people to comment GEAR. The automation listens on that Reel, matching the whole word, with tap first on."
        lines={[
          { who: "them", text: "GEAR 🙌" },
          { who: "note", text: "Public reply under the comment: “Sent you a DM 👋”" },
          { who: "you", text: "Hi! Here's the gear list from the studio tour. Tap below and I'll send the link." },
          { who: "tap", text: "Send me the link" },
          { who: "you", text: "Here you go: the full list with links. Reply here if you have a question about any of it." },
        ]}
      />

      <GuideH2>See what it does</GuideH2>
      <p>
        Comment automations also count public replies posted, taps on a tap-first opening, and what is waiting in the queue right now. Each automation shows figures from its own run log: how often it ran, the DMs sent, how many people replied within 24
        hours, and anything skipped, with the reason. A flow adds a funnel for each step, with link clicks counted through a
        tracked link, and a split shows how each branch did. The Activity page lists every failed send with the reason in plain
        words and one action to fix it.
      </p>

      <GuideH2>Mistakes to avoid</GuideH2>
      <Callout tone="info">
        <ul>
          <li>A keyword people type by accident, such as “yes” or “nice”. Pick a short word that only means one thing.</li>
          <li>The same public reply on every comment. Write a few and let them rotate.</li>
          <li>Asking for a follow before sending the link. It breaks Meta&apos;s rules and annoys people.</li>
          <li>Promising something in the caption that the DM doesn&apos;t deliver, such as a code that has expired.</li>
        </ul>
      </Callout>
    </>
  );
}

const COMMENT_TO_DM: AutomationPage = {
  path: "/instagram/comment-to-dm",
  channel: "instagram",
  name: "Instagram comment to DM",
  title: "Instagram comment to DM automation",
  description:
    "Auto-reply to Instagram comments with a DM: keywords, match modes, tap-first buttons, Meta's 7-day private-reply rule, plan limits and setup steps.",
  h1: "Auto-reply to Instagram comments with a DM",
  lede: "Someone comments your keyword and gets the link in a DM, with a public reply if you want one. Here is how it works, the rules Meta sets, and how to set one up.",
  queries: ["how to auto-reply to Instagram comments with a DM", "Instagram comment to DM", "Instagram auto DM on comment"],
  icon: MessageCircle,
  scene: "comments",
  published: "2026-10-31",
  updated: "2026-10-31",
  sections: ["How it works in Amplychat", "Meta's rules for replying to comments", "Set it up", "An example", "See what it does", "Mistakes to avoid"],
  Body: CommentToDmBody,
  limits: [ROW_AUTOMATIONS, ROW_STEPS, ROW_AI_AUTOMATIONS],
  credits: [CREDIT_FIXED, CREDIT_AUTOMATION_AI, CREDIT_READ],
  faq: [
    {
      question: "What happens to comments that arrive faster than Instagram allows?",
      answer:
        "They wait in a queue for that account and go out as Meta's limit of 750 private replies an hour allows, oldest first unless you choose newest first. A comment still waiting after 7 days is skipped, because Instagram no longer allows a private reply to it.",
    },
    {
      question: "Can one automation answer every post I publish from now on?",
      answer:
        "Yes, with a keyword: choose all posts. An automation that answers any comment needs chosen posts or your next post, so it doesn't DM everyone who comments anywhere.",
    },
    {
      question: "Can the DM include a photo?",
      answer:
        "Not the first one. Instagram sends a private reply to a comment as text with buttons only. With tap first on, the message after their tap is a normal DM and can carry an image.",
    },
  ],
  sources: [META.privateReplies, META.limits, META.policy],
  guide: GUIDE_COMMENTS,
  audience: FOR_CREATORS,
  related: [SAFETY, { label: "Comment intelligence", href: "/features/comment-intelligence" }],
};

// ---------------------------------------------------------------- Instagram: story replies and mentions

function StoryRepliesBody() {
  return (
    <>
      <p>
        When someone replies to your Instagram Story, the reply lands in your DMs. When someone mentions you in their own Story,
        Instagram sends you a message about it too. Both are moments when a person has just paid attention to you, and both can
        start an automation: a thank-you, the link from the Story, a discount for sharing, or a question to find out what they
        need. Because the person wrote first, the reply arrives as a welcome answer rather than a cold message.
      </p>

      <GuideH2>How it works in Amplychat</GuideH2>
      <StepCards
        items={[
          // Trigger story_reply (GR-06): keywords optional; any story or chosen stories (up to 20).
          {
            icon: Reply,
            body: (
              <>
                <strong>Story reply</strong>: answer every reply, or only replies with one of your keywords. Listen on any Story or on
                chosen ones; a chosen Story stops matching when it expires after 24 hours.
              </>
            ),
          },
          // Trigger story_mention (GR-07): needs nothing but a message; a Mentions page lists them.
          { icon: AtSign, body: <><strong>Story mention</strong>: someone tags you in their Story. It needs nothing but a message, and the Mentions page under Comments lists every mention.</> },
          // story_heart: Instagram's heart sticker ahead of the message.
          { icon: Heart, body: <><strong>A heart back</strong>: a story reply automation can send Instagram&apos;s heart reaction before its message.</> },
        ]}
      />
      <p>
        A story reply also starts your DM keyword automations, keyword ones first and then those that answer any reply. A reply
        that is only the heart (a Story like) starts nothing, and a mention never starts a keyword automation. Because these are
        DMs, not private replies, the message can carry an image and up to three link buttons, and it can open a longer flow
        that asks a question or saves an email.
      </p>
      <p>
        Story replies and mentions also arrive in the inbox as ordinary conversations, so the AI can draft or send the next answer
        from your knowledge once the automation has done its part.
      </p>

      <GuideH2>{"Meta's rules for story messages"}</GuideH2>
      <Callout tone="note" title="The messaging window">
        <p>
          A story reply or mention is the person writing to you first, which opens Instagram&apos;s standard messaging window:{" "}
          <strong>24 hours</strong> in which you can reply. Each new message from them starts it again.
        </p>
      </Callout>
      <ul>
        <li>
          <strong>Rate limits.</strong> Meta allows 100 text messages a second for each account; {N} paces every send through a
          queue, so a Story that takes off is answered steadily.
        </li>
        <li>
          <strong>Say it&apos;s automated.</strong> Meta asks automated chats to say so. Your workspace&apos;s disclosure line is added to
          automated messages.
        </li>
        <li>
          <strong>Facebook Pages</strong> have no Stories in Messenger, so these two triggers are for Instagram only.
        </li>
      </ul>

      <GuideH2>Set it up</GuideH2>
      <Checklist>
        <li>Create an automation and choose “Instagram story reply” or “Instagram story mention”.</li>
        <li>For story replies, add keywords or answer every reply, and pick any Story or the ones you want.</li>
        <li>Write the message, and turn on the heart if you like.</li>
        <li>Preview it and switch it on. Post a Story that tells people what to reply.</li>
      </Checklist>

      <GuideH2>An example</GuideH2>
      <ExampleThread
        title="A Story poll for a new colour"
        setting="A made-up shop posts a Story: “Reply PINK to get the new colour first.” A story reply automation listens on that Story for the keyword, with the heart on."
        lines={[
          { who: "them", text: "PINK 💗 (replied to your story)" },
          { who: "note", text: "The heart reaction goes first." },
          { who: "you", text: "You're on the list! The pink tote drops Friday at 10:00. Want a reminder? Tap below." },
          { who: "tap", text: "Remind me" },
          { who: "you", text: "Done. We'll message you here on Friday morning." },
        ]}
      />

      <GuideH2>See what it does</GuideH2>
      <p>
        Each automation shows figures from its own run log: how often it ran, the DMs sent, how many people replied within 24
        hours, and anything skipped, with the reason. A flow adds a funnel for each step, with link clicks counted through a
        tracked link, and a split shows how each branch did. The Activity page lists every failed send with the reason in plain
        words and one action to fix it.
      </p>

      <GuideH2>Mistakes to avoid</GuideH2>
      <Callout tone="info">
        <ul>
          <li>Answering every story reply with a sales message. Use keywords, or a reply that fits any reaction.</li>
          <li>Thanking mentions with a generic line. Name what they shared, or offer something for it.</li>
          <li>Promising a reminder days later. The window closes 24 hours after their last message, unless they write again.</li>
        </ul>
      </Callout>
    </>
  );
}

const STORY_REPLIES: AutomationPage = {
  path: "/instagram/story-replies",
  channel: "instagram",
  name: "Story replies and mentions",
  title: "Instagram story reply and mention automation",
  description:
    "Automate replies to Instagram Story replies and mentions: keywords or any reply, chosen Stories, a heart back, the 24-hour window and setup steps.",
  h1: "Automate replies to Instagram Story replies and mentions",
  lede: "Thank everyone who mentions you, and answer Story replies with the link, a code or a question. Here is how the two triggers work and what Instagram allows.",
  queries: ["Instagram story reply automation", "auto DM when someone mentions you in their story", "Instagram story mention auto reply"],
  icon: Reply,
  scene: "story",
  published: "2026-10-31",
  updated: "2026-10-31",
  sections: ["How it works in Amplychat", "Meta's rules for story messages", "Set it up", "An example", "See what it does", "Mistakes to avoid"],
  Body: StoryRepliesBody,
  limits: [ROW_AUTOMATIONS, ROW_STEPS, planRow("Instagram accounts", "accounts_per_platform")],
  credits: [CREDIT_FIXED, CREDIT_AUTOMATION_AI, CREDIT_READ],
  faq: [
    {
      question: "Does a heart on my Story start the automation?",
      answer: "No. A reply that is only the heart is a Story like, not a message, so story reply automations don't answer it.",
    },
    {
      question: "Can I answer replies to one Story only?",
      answer:
        "Yes. Choose up to 20 Stories, or answer any Story. A chosen Story stops matching once it expires after 24 hours, so a later Story needs its own choice.",
    },
    {
      question: "Where do I see everyone who mentioned me?",
      answer:
        "On the Mentions page under Comments, and each mention is also a conversation in the inbox, so you can reply by hand when you want to.",
    },
  ],
  sources: [META.messaging, META.limits, META.policy],
  guide: GUIDE_COMMENTS,
  audience: FOR_CREATORS,
  related: [{ label: "Instagram DM keyword auto-reply", href: "/instagram/dm-keywords" }],
};

// ---------------------------------------------------------------- Instagram: DM keywords

function DmKeywordsBody() {
  return (
    <>
      <p>
        A DM keyword automation answers a direct message that contains a word you choose: PRICE, MENU, BOOK, SIZE. It is the
        quickest way to answer the questions you get twenty times a day with the same link, price list or booking page, and to
        start a longer flow when the question needs one.
      </p>

      <GuideH2>How it works in Amplychat</GuideH2>
      <p>
        Add up to 50 keywords to an automation and choose how they match. Text and keywords are compared without case, accents or
        extra spaces, and words in any script count.
      </p>
      <StepCards
        columns={3}
        items={[
          // services/automations/matching.py MatchMode: word, exact, contains.
          { icon: WholeWord, body: <><strong>Whole word</strong>: “price” matches “What&apos;s the PRICE?” but not “priceless”. The default.</> },
          { icon: Equal, body: <><strong>Exact message</strong>: the whole message is the keyword, ignoring punctuation around it.</> },
          { icon: Asterisk, body: <><strong>Contains</strong>: the keyword can sit inside a longer word.</> },
        ]}
      />
      <p>
        When a message matches, the automation sends your message (text, an image and up to three link buttons), runs a flow, or
        on Pro writes an AI reply from your knowledge. Once an automation has answered, the inbox AI leaves that message alone.
      </p>
      <ul>
        <li>
          <strong>Order.</strong> Chats from an entry link or an ad go first, then keyword automations by the priority you set,
          then a welcome for someone&apos;s first message, then a default reply when nothing else matched and AI replies are off.
        </li>
        <li>
          <strong>Cooldown.</strong> Each automation answers the same person at most once in 24 hours by default; set anything from
          none to 72 hours.
        </li>
        <li>
          <strong>Hours.</strong> Run it at any time, only inside your business hours, or only outside them.
        </li>
      </ul>

      <GuideH2>{"Meta's rules for DMs"}</GuideH2>
      <Callout tone="note" title="The messaging window">
        <p>
          A business can reply to an Instagram DM within <strong>24 hours</strong> of the customer&apos;s last message. A keyword
          automation always answers a message they just sent, so it is always inside the window.
        </p>
      </Callout>
      <ul>
        <li>
          Meta also has a 7-day window for replies a person types, the human agent tag. {N} uses it only once Meta approves it for
          our app; until then, a conversation older than 24 hours waits for the customer to write again.
        </li>
        <li>Meta allows 100 text messages a second for each account, and {N} paces sends through a queue.</li>
        <li>Meta asks automated chats to say so; your workspace&apos;s disclosure line goes on automated messages.</li>
      </ul>

      <GuideH2>Set it up</GuideH2>
      <Checklist>
        <li>Create an automation and choose “Instagram DM keyword”.</li>
        <li>Add the keywords people actually type, with their common spellings.</li>
        <li>Pick the match mode; keep “Whole word” unless you have a reason not to.</li>
        <li>Write the reply, add a link button, and set the cooldown and priority.</li>
        <li>Preview it with a test message, then switch it on.</li>
      </Checklist>

      <GuideH2>An example</GuideH2>
      <p>How three messages match the keyword “price” in each mode:</p>
      <table>
        <thead>
          <tr>
            <th scope="col">Message</th>
            <th scope="col">Whole word</th>
            <th scope="col">Exact message</th>
            <th scope="col">Contains</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Price?</th>
            <td>Matches</td>
            <td>Matches</td>
            <td>Matches</td>
          </tr>
          <tr>
            <th scope="row">What&apos;s the price of the tote?</th>
            <td>Matches</td>
            <td>No</td>
            <td>Matches</td>
          </tr>
          <tr>
            <th scope="row">Is this priceless?</th>
            <td>No</td>
            <td>No</td>
            <td>Matches</td>
          </tr>
        </tbody>
      </table>
      <ExampleThread
        title="A price list on request"
        setting="A made-up bakery answers PRICE and MENU, matching the whole word, with a 24-hour cooldown."
        lines={[
          { who: "them", text: "hi! what's the price for a 1 kg cake?" },
          { who: "you", text: "Hi! Here's our full price list, with sizes and flavours. Tap to see it, or reply with your date to order." },
          { who: "note", text: "A link button opens the price list. Their next question goes to the inbox, where the AI drafts the answer." },
        ]}
      />

      <GuideH2>See what it does</GuideH2>
      <p>
        Each automation shows figures from its own run log: how often it ran, the DMs sent, how many people replied within 24
        hours, and anything skipped, with the reason. A flow adds a funnel for each step, with link clicks counted through a
        tracked link, and a split shows how each branch did. The Activity page lists every failed send with the reason in plain
        words and one action to fix it.
      </p>

      <GuideH2>Mistakes to avoid</GuideH2>
      <Callout tone="info">
        <ul>
          <li>“Contains” on short keywords: “hi” would match “this” and “ship”.</li>
          <li>A cooldown of none on a long message. Someone who asks twice gets the same wall of text twice.</li>
          <li>Two automations with the same keyword and no priority. Set which one wins.</li>
        </ul>
      </Callout>
    </>
  );
}

const DM_KEYWORDS: AutomationPage = {
  path: "/instagram/dm-keywords",
  channel: "instagram",
  name: "Instagram DM keyword auto-reply",
  title: "Instagram DM keyword auto-reply",
  description:
    "Auto-reply to Instagram DMs that contain a keyword: three match modes, priority and cooldowns, the 24-hour window, plan limits and an example.",
  h1: "Instagram DM keyword auto-reply: answer the words customers send",
  lede: "Answer PRICE, MENU or BOOK the moment someone sends it, with a link, a flow or an AI reply. Here is how matching works and what Instagram allows.",
  queries: ["Instagram DM keyword auto reply", "Instagram auto reply to DMs with keywords", "Instagram DM automation keyword"],
  icon: Send,
  scene: "keywords",
  published: "2026-10-31",
  updated: "2026-10-31",
  sections: ["How it works in Amplychat", "Meta's rules for DMs", "Set it up", "An example", "See what it does", "Mistakes to avoid"],
  Body: DmKeywordsBody,
  limits: [ROW_AUTOMATIONS, ROW_AI_AUTOMATIONS, ROW_STEPS],
  credits: [CREDIT_FIXED, CREDIT_AUTOMATION_AI, CREDIT_READ],
  faq: [
    {
      question: "What if a DM matches two keyword automations?",
      answer:
        "The one with the lower priority number answers; with equal priority, the older automation does. Only one keyword automation answers a message.",
    },
    {
      question: "Does the AI reply on top of a keyword automation?",
      answer:
        "No. Once an automation has answered a message, the inbox AI leaves that message alone. Their next message is handled as usual.",
    },
    {
      question: "Can I answer DMs that match no keyword?",
      answer:
        "Yes, with a default reply, which answers a DM nothing else matched while AI replies are off for that conversation. With AI on Suggest or Auto, the AI answers instead.",
    },
  ],
  sources: [META.messaging, META.limits, META.policy],
  guide: GUIDE_DMS,
  audience: FOR_BUSINESSES,
  related: [{ label: "Instagram conversation starters", href: "/instagram/conversation-starters" }],
};

// ---------------------------------------------------------------- Instagram: conversation starters

function StartersBody() {
  return (
    <>
      <p>
        Conversation starters, which Meta calls ice breakers, are up to four questions shown when someone opens a new chat with
        your account in the Instagram app: “What are your prices?”, “Do you deliver?”, “Book a session”. A tap sends the question,
        and your answer can arrive at once. They help people who don&apos;t know what to ask, and they tell you exactly what each
        person wants.
      </p>

      <GuideH2>How it works in Amplychat</GuideH2>
      <StepCards
        items={[
          // services/ice_breakers.py: MAX_STARTERS 4, QUESTION_CHARS 80, each question different.
          { icon: ListChecks, body: <><strong>Up to four questions</strong> per account, each up to 80 characters and each different.</> },
          // Each maps to an automation on the ice_breaker trigger, or to "answer with AI".
          {
            icon: MessagesSquare,
            body: (
              <>
                <strong>An answer for each</strong>: an automation that starts from a conversation starter (a message, a flow), or the
                AI answering from your knowledge.
              </>
            ),
          },
          // save(): pushed to Instagram, replacing what's there; a failed push keeps the list and shows why.
          { icon: Send, body: <><strong>Saved to Instagram</strong>: saving replaces the account&apos;s starters on Instagram. If Instagram refuses, the list is kept and the reason shown, and Sync again retries.</> },
          // A position keeps its id, so a starter already on someone's screen keeps working.
          { icon: Hand, body: <><strong>Safe to edit</strong>: change a question and the starter keeps working for people who already see it.</> },
        ]}
      />
      <p>
        Set them on the Conversation starters page under Automations. A starter set to answer with AI leaves the message to the
        inbox AI, which drafts on Suggest or replies by itself on Auto (Pro), and hands it to you when the answer isn&apos;t in your
        knowledge. Facebook Pages can have conversation starters in Messenger too, once Meta approves Facebook for {N}.
      </p>

      <p>
        Good starters are the questions you already answer every day, in the words customers use: “What are your prices?” rather
        than “Pricing information”. Keep each to one idea, so the answer can be short and complete. If people often ask
        something you can&apos;t answer in one message, point that starter to a flow that asks a question first, such as the day
        or the size, and then sends the right reply.
      </p>

      <GuideH2>{"Meta's rules for ice breakers"}</GuideH2>
      <Callout tone="note" title="What Instagram allows">
        <p>
          <strong>At most four questions</strong> per account, and they don&apos;t show on desktop: only in the mobile app.
        </p>
      </Callout>
      <ul>
        <li>
          A tap is the person writing to you, so it opens the standard <strong>24-hour</strong> messaging window and your answer is
          always allowed.
        </li>
        <li>Meta asks automated chats to say so. An automation&apos;s message carries your workspace&apos;s disclosure line.</li>
      </ul>

      <GuideH2>Set it up</GuideH2>
      <Checklist>
        <li>Create the automations first, each with the “Instagram conversation starter” trigger, or plan to answer with AI.</li>
        <li>Open Automations, then Conversation starters, and pick the account.</li>
        <li>Write up to four short questions in the words your customers use.</li>
        <li>Map each to its automation or to the AI, then save. Check the sync status says it worked.</li>
      </Checklist>

      <GuideH2>An example</GuideH2>
      <ExampleThread
        title="A salon's four starters"
        setting="A made-up salon sets: “See prices”, “Book an appointment”, “Where are you?” and “Ask a question”. The first three start automations; the last answers with AI."
        lines={[
          { who: "tap", text: "Book an appointment" },
          { who: "you", text: "Lovely! Which day suits you? Tap one, or tell us another." },
          { who: "tap", text: "Saturday" },
          { who: "you", text: "Saturday it is. Here's the booking page with every free slot." },
        ]}
      />

      <GuideH2>See what it does</GuideH2>
      <p>
        Every tap on a starter starts its automation, so the figures tell you which questions people choose most. Each automation shows figures from its own run log: how often it ran, the DMs sent, how many people replied within 24
        hours, and anything skipped, with the reason. A flow adds a funnel for each step, with link clicks counted through a
        tracked link, and a split shows how each branch did. The Activity page lists every failed send with the reason in plain
        words and one action to fix it.
      </p>

      <GuideH2>Mistakes to avoid</GuideH2>
      <Callout tone="info">
        <ul>
          <li>Questions in your words rather than your customers&apos;. Use the ones you get most.</li>
          <li>Four starters that all lead to the same link. Each should answer something different.</li>
          <li>Deleting an automation a starter points to. Map the starter to something else first.</li>
        </ul>
      </Callout>
    </>
  );
}

const STARTERS: AutomationPage = {
  path: "/instagram/conversation-starters",
  channel: "instagram",
  name: "Instagram conversation starters",
  title: "Instagram conversation starters (ice breakers)",
  description:
    "Set up to four Instagram conversation starters (ice breakers), each answered by an automation or the AI. Meta's rules, setup steps and an example.",
  h1: "Instagram conversation starters: questions people tap to start a chat",
  lede: "Give people up to four questions to tap when they open a chat with you, and answer each one at once. Here is how they work and what Instagram allows.",
  queries: ["Instagram conversation starters", "Instagram ice breakers", "Instagram FAQ questions in DMs"],
  icon: ListChecks,
  scene: "starters",
  published: "2026-10-31",
  updated: "2026-10-31",
  sections: ["How it works in Amplychat", "Meta's rules for ice breakers", "Set it up", "An example", "See what it does", "Mistakes to avoid"],
  Body: StartersBody,
  limits: [ROW_AUTOMATIONS, ROW_MODES, ROW_STEPS],
  credits: [CREDIT_FIXED, `A starter answered by the inbox AI: ${CREDIT_DRAFT.charAt(0).toLowerCase()}${CREDIT_DRAFT.slice(1)}`, CREDIT_READ],
  faq: [
    {
      question: "Why can't I see my conversation starters on my laptop?",
      answer: "Instagram shows them only in its mobile app, not on desktop. Open a new chat with your account on a phone to check them.",
    },
    {
      question: "Can I have more than four?",
      answer: "No. Instagram allows four per account. Use the four questions you're asked most, and let the AI handle the rest.",
    },
    {
      question: "What if a starter's sync fails?",
      answer: "The list is kept in Amplychat with the reason Instagram gave, and Instagram keeps showing what it had. Fix the cause, then use Sync again.",
    },
  ],
  sources: [META.iceBreakers, META.messaging, META.policy],
  guide: GUIDE_DMS,
  audience: FOR_BUSINESSES,
  related: [{ label: "Instagram DM keyword auto-reply", href: "/instagram/dm-keywords" }],
};

// ---------------------------------------------------------------- WhatsApp: auto-reply

function WhatsAppBody() {
  return (
    <>
      <p>
        On the WhatsApp Business Platform, an auto-reply is a message your system sends when a customer writes, without anyone
        typing it. Done well, it answers the question itself, at any hour, and passes the rest to a person. Done badly, it is a
        “thanks, we&apos;ll get back to you” that nobody reads. {N} does the first kind, within the rules WhatsApp sets.
      </p>

      <GuideH2>How it works in Amplychat</GuideH2>
      <StepCards
        items={[
          // models/ai.py AI modes per account; Auto is Pro (plan-table ai_modes).
          { icon: Send, body: <><strong>Off, Suggest or Auto</strong> for the number. Suggest drafts each reply for you to send; Auto replies by itself when it is confident, and is part of Pro.</> },
          // Answers only from knowledge; escalation reasons; knowledge gaps.
          { icon: KeyRound, body: <><strong>Answers from your knowledge</strong>: your text, questions and answers, files and website pages. When the answer isn&apos;t there, it goes to Needs you.</> },
          // services/business_hours.py: auto_mode always or out_of_hours; the away message once per closed window.
          { icon: MapPin, body: <><strong>Business hours</strong>: let Auto answer at any hour or only while you&apos;re closed, and send an away message once each time you close.</> },
          // services/takeover: 2 hours by default.
          { icon: Hand, body: <><strong>You can step in</strong>: when you reply yourself, the AI pauses on that chat for 2 hours by default.</> },
        ]}
      />
      <p>
        Keyword and comment automations are for Instagram and Facebook; on WhatsApp the AI and the away message do the answering.
        Timed follow-ups (sequences) send their text while the 24-hour window is open. WhatsApp broadcasts are built and coming
        soon, after our review of the consent rules.
      </p>

      <GuideH2>{"WhatsApp's 24-hour window and templates"}</GuideH2>
      <Callout tone="note" title="The customer service window">
        <p>
          When a customer messages you, a <strong>24-hour customer service window</strong> starts, and it restarts each time they
          write again. Inside it you can send any reply. Once it closes, you can only send{" "}
          <strong>templates Meta has approved</strong>.
        </p>
      </Callout>
      <ul>
        <li>
          An auto-reply always answers a message the customer just sent, so it is inside the window. {N} shows when each
          window closes.
        </li>
        <li>
          After that, the inbox offers the approved templates from your WhatsApp Business account, so you can restart the
          conversation in one tap.
        </li>
        <li>
          <strong>Fees.</strong> Meta charges for templates per delivered message, by category and the recipient&apos;s country. Since 1
          October 2026, each number also has 1,000 free service messages a month, and Meta charges for service messages after that.
          You pay Meta directly, and {N} adds no markup.
        </li>
      </ul>

      <GuideH2>Where your team comes in</GuideH2>
      <p>
        The chats the AI hands over don&apos;t sit in a phone. They wait in Needs you in the shared inbox, where a conversation can
        be assigned by hand or in turn to the next available member, and saved replies cover the answers you type often. When a
        chat needs someone, {N} notifies the team in the app, by email or as a push notification. Each answered question you
        add to your knowledge is one the AI can answer next time, and the knowledge gaps list shows which ones to add first.
      </p>

      <GuideH2>Set it up</GuideH2>
      <Checklist>
        <li>Connect a number your business owns through Meta&apos;s Embedded Signup.</li>
        <li>Add your knowledge: prices, delivery, opening hours, your policies, your website.</li>
        <li>Test questions in the knowledge page until the answers are right.</li>
        <li>Set the number to Suggest for a few days, then to Auto when the drafts need no edits.</li>
        <li>Add business hours and an away message for the times you&apos;re closed.</li>
      </Checklist>

      <GuideH2>An example</GuideH2>
      <ExampleThread
        title="A delivery question at night"
        setting="A made-up home goods shop has its number on Auto, only out of hours, with an away message."
        lines={[
          { who: "them", text: "Hi, do you deliver to Pune? And how long does it take?" },
          { who: "you", text: "Hi! Yes, we deliver across India. Orders ship within 2 working days and arrive in 3 to 5 days." },
          { who: "them", text: "Can I return it if the colour is off?" },
          { who: "note", text: "Returns need a person: the chat goes to Needs you, and the team answers in the morning, inside the window." },
        ]}
      />

      <GuideH2>Mistakes to avoid</GuideH2>
      <Callout tone="info">
        <ul>
          <li>Turning on Auto before the knowledge covers your common questions.</li>
          <li>Leaving a question unanswered for more than a day. After 24 hours, only a template can reach them.</li>
          <li>An away message that promises a reply time you can&apos;t keep.</li>
        </ul>
      </Callout>
    </>
  );
}

const WHATSAPP: AutomationPage = {
  path: "/whatsapp/auto-reply",
  channel: "whatsapp",
  name: "WhatsApp auto-reply",
  title: "WhatsApp auto-reply with AI and templates",
  description:
    "Auto-reply on WhatsApp with AI that answers from your knowledge: Suggest or Auto, business hours, the 24-hour window, templates and Meta's fees.",
  h1: "WhatsApp auto-reply: AI answers inside the 24-hour window, templates after",
  lede: "Answer WhatsApp messages at any hour from your own knowledge, and hand the rest to your team. Here is how it works with WhatsApp's window, templates and fees.",
  queries: ["WhatsApp auto reply", "WhatsApp Business API auto reply", "WhatsApp AI auto reply 24 hour window"],
  icon: MessageCircle,
  scene: "modes",
  published: "2026-10-31",
  updated: "2026-10-31",
  sections: ["How it works in Amplychat", "WhatsApp's 24-hour window and templates", "Where your team comes in", "Set it up", "An example", "Mistakes to avoid"],
  Body: WhatsAppBody,
  limits: [ROW_MODES, ROW_CREDITS, planRow("WhatsApp numbers", "accounts_per_platform")],
  credits: [CREDIT_DRAFT, CREDIT_READ, "An away message uses no AI credits. Meta's WhatsApp fees are separate and paid to Meta."],
  faq: [
    {
      question: "Does the AI reply on WhatsApp while I'm open?",
      answer:
        "Your choice. Auto can answer at any hour, or only while you're closed, so your team answers during the day and the AI covers nights and weekends.",
    },
    {
      question: "Will customers get an away message and an AI reply?",
      answer:
        "No. The away message is skipped for a chat the AI will answer on Auto, and it goes once each time you close, not on every message.",
    },
    {
      question: "Can I create WhatsApp templates in Amplychat?",
      answer:
        "Not yet. Templates are created and approved in your WhatsApp Business account with Meta; once approved, they show in Amplychat's inbox within minutes.",
    },
  ],
  sources: [META.waWindow, META.waPricing],
  guide: GUIDE_WHATSAPP,
  audience: FOR_BUSINESSES,
  related: [{ label: "WhatsApp's charges on the pricing page", href: "/pricing" }, { label: "The AI inbox", href: "/features/ai-inbox" }],
};

// ---------------------------------------------------------------- Website chat

function WebsiteChatBody() {
  return (
    <>
      <p>
        An AI chat for your website is a chat window on your pages that answers visitors straight away, from what your business
        knows, and brings a person in when it should. {N}&apos;s website chat is on every plan, and its chats land in the same inbox
        as your Instagram and WhatsApp messages, with the same AI and the same team.
      </p>

      <GuideH2>How it works in Amplychat</GuideH2>
      <StepCards
        items={[
          // WidgetSettingsPage: one line of code before </body>; widget_settings.allowed_domains (up to 20).
          { icon: PanelsTopLeft, body: <><strong>One line of code</strong> on your site, and a list of up to 20 domains where it may load. It refuses to load anywhere else.</> },
          // widget_settings: title, greeting, accent colour, left or right.
          { icon: MessageCircle, body: <><strong>Your look</strong>: the title, the greeting, your colour, and the left or right corner.</> },
          // email_capture off / optional / required; marketing consent with the words shown as evidence.
          { icon: AtSign, body: <><strong>Email when you want it</strong>: never, after the first message, or before it, with an optional marketing consent box.</> },
          // AI modes, knowledge, escalation; ingest as on Instagram.
          { icon: KeyRound, body: <><strong>The same AI</strong>: Suggest or Auto (Pro), answers from your knowledge, and Needs you when it doesn&apos;t know.</> },
        ]}
      />
      <p>
        The AI can read your website&apos;s own pages as knowledge, so a visitor asking about delivery gets the answer from your
        delivery page. Business hours and an away message work here too. On Pro and Max you can remove the “Powered by {N}” line.
      </p>
      <p>
        A visitor who comes back on the same browser sees their earlier messages, so a conversation can pick up where it stopped.
        Each visitor gets a signed session for your domain only, and there are limits on how often one visitor or one address
        can send, so the widget can&apos;t be used to flood your inbox.
      </p>

      <GuideH2>No 24-hour window here</GuideH2>
      <Callout tone="means" title="What this means for you">
        <p>
          Website chat doesn&apos;t go through Meta, so <strong>no messaging window applies</strong>: you can reply hours later, and the
          widget shows the answer whenever the visitor looks. Meta&apos;s rules apply to your Instagram and WhatsApp chats, not to
          this one.
        </p>
      </Callout>
      <ul>
        <li>
          When a visitor ticks the marketing box, {N} records the exact words shown, the page and the time. An unticked box
          records nothing.
        </li>
        <li>New chats each day are capped by plan; over the cap, the visitor is asked to try again later.</li>
      </ul>

      <GuideH2>Where the chats go</GuideH2>
      <p>
        Every website chat is a conversation in the same inbox as Instagram and WhatsApp, tagged with its intent, sentiment and
        a lead score, so a visitor ready to buy stands out. A visitor who leaves an email becomes a contact with that address,
        and a new lead in the leads list. Your team can be notified in the app, by email or as a push notification when a chat
        needs them, and webhooks can send each new contact to your own tools.
      </p>
      <p>
        Because the same knowledge answers every channel, an answer you add after a website question also helps on Instagram
        and WhatsApp. The knowledge gaps list shows the questions the AI couldn&apos;t answer, so you know what to add next.
      </p>

      <GuideH2>Set it up</GuideH2>
      <Checklist>
        <li>Open Settings, then Website chat, and set the title, greeting and colour.</li>
        <li>Add the domains where the widget may load.</li>
        <li>Copy the line of code and paste it before the closing body tag of your site.</li>
        <li>Choose when to ask for an email, and add your website&apos;s pages to the knowledge.</li>
        <li>Set business hours and an away message for the times nobody can answer.</li>
        <li>Send a test message from your site and answer it from the inbox.</li>
      </Checklist>

      <GuideH2>An example</GuideH2>
      <ExampleThread
        title="A sizing question on a product page"
        setting="A made-up clothing shop has the widget on Auto, with email asked after the first message."
        lines={[
          { who: "them", text: "Does the linen shirt run small?" },
          { who: "you", text: "It runs true to size. If you're between sizes, our size guide suggests the larger one for a relaxed fit." },
          { who: "note", text: "The widget asks for an email so the shop can follow up if the visitor leaves." },
          { who: "them", text: "Can I get it in a custom length?" },
          { who: "note", text: "Not in the knowledge: the chat goes to Needs you, and the AI doesn't guess." },
        ]}
      />

      <GuideH2>Mistakes to avoid</GuideH2>
      <Callout tone="info">
        <ul>
          <li>Requiring an email before the first message on a page where people only want a quick answer.</li>
          <li>Forgetting to add a new domain. The widget won&apos;t load on a host that isn&apos;t listed.</li>
          <li>Leaving the default greeting. Say what you can help with.</li>
          <li>Letting the knowledge go stale. When prices or policies change, update it the same day: the AI answers only from what is there.</li>
        </ul>
      </Callout>
    </>
  );
}

const WEBSITE_CHAT: AutomationPage = {
  path: "/website-chat",
  channel: "web",
  name: "AI chat for your website",
  title: "AI chat widget for your website",
  description:
    "Add an AI chat widget to your website that answers from your own knowledge, asks for emails and hands off to your team, in one inbox with Instagram.",
  h1: "AI chat for your website, answered from your own knowledge",
  lede: "A chat widget on your own site that answers visitors from what your business knows, and brings you in when it should. On every plan.",
  queries: ["AI chat for website", "AI chatbot widget for small business website", "website live chat with AI"],
  icon: PanelsTopLeft,
  scene: "widget",
  published: "2026-10-31",
  updated: "2026-10-31",
  sections: ["How it works in Amplychat", "No 24-hour window here", "Where the chats go", "Set it up", "An example", "Mistakes to avoid"],
  Body: WebsiteChatBody,
  limits: [
    planRow("New website chats a day", "widget_conversations_daily"),
    ROW_MODES,
    planRow("Website pages read", "crawl_pages"),
    planRow("Remove “Powered by”", "widget_remove_branding"),
  ],
  credits: [CREDIT_DRAFT, CREDIT_READ, "Each test question in the knowledge page uses one credit."],
  faq: [
    {
      question: "Does the widget work on Shopify, WordPress or Wix?",
      answer:
        "It works on any site where you can paste a line of code before the closing body tag and list the domain in the widget's settings.",
    },
    {
      question: "What happens when I've used the day's chats?",
      answer: "New visitors are asked to try again later; chats already open carry on. The count starts again the next day.",
    },
    {
      question: "Can I put the same chat on more than one site?",
      answer:
        "Yes. List up to 20 domains in the widget's settings, including every subdomain of one with a wildcard such as *.example.com. The chats from all of them arrive in the same inbox.",
    },
    {
      question: "Can visitors talk to a person?",
      answer:
        "Yes. Any chat can be answered from the inbox, and anything the AI can't answer from your knowledge goes to Needs you for your team.",
    },
  ],
  sources: [],
  guide: GUIDE_DMS,
  audience: FOR_BUSINESSES,
  related: [{ label: "The AI inbox", href: "/features/ai-inbox" }],
};

/** Every page, in the hub's order: Instagram, then WhatsApp, then website chat. */
export const AUTOMATION_PAGES: readonly AutomationPage[] = [COMMENT_TO_DM, STORY_REPLIES, DM_KEYWORDS, STARTERS, WHATSAPP, WEBSITE_CHAT];

export function automationPage(path: string): AutomationPage {
  const page = AUTOMATION_PAGES.find((item) => item.path === path);
  if (!page) throw new Error(`No automation page at ${path}`);
  return page;
}

/** "31 October 2026", as the guides write dates. */
export function automationDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

