import Link from "next/link";

import { SITE_NAME } from "../site";
import { GUIDE_AUTHOR, type Guide } from "./types";

const N = SITE_NAME;

function Body() {
  return (
    <>
      <p>
        You have seen it under Reels everywhere: “Comment LINK and I&apos;ll DM it to you.” A few seconds after you comment,
        a message arrives with the product page, the recipe or the discount code. For a business or a creator it does two jobs at once. The
        post gets comments, which helps it reach more people, and every interested person lands in your DMs, where a sale
        actually happens.
      </p>
      <p>
        This guide covers how comment-to-DM automations work on Instagram, the rules they have to follow, and how to set one
        up so it feels helpful rather than spammy.
      </p>

      <h2>How it works</h2>
      <p>Every comment-to-DM automation has the same four parts:</p>
      <ol>
        <li>
          <strong>Where it listens</strong>: one post or Reel, a few chosen ones, or all of them.
        </li>
        <li>
          <strong>What it listens for</strong>: a keyword such as LINK, PRICE or SIZE, or any comment at all.
        </li>
        <li>
          <strong>A public reply</strong> under the comment, if you want one, such as “Sent you a DM!”, so other people can
          see you answered.
        </li>
        <li>
          <strong>The private message</strong>: the DM that carries what they asked for.
        </li>
      </ol>
      <p>
        That is the whole idea. The details are where most automations go wrong, so the rest of this guide is about the
        details.
      </p>

      <h2>The Instagram rules behind it</h2>
      <p>
        Instagram allows a business to answer a comment with a private message, but only one message per comment, and only
        within 7 days of the comment. After that one message, you can send more only once the person replies, which
        opens the usual 24-hour window for DMs.
      </p>
      <p>This shapes good automations in two ways:</p>
      <ul>
        <li>
          <strong>Ask for a tap first.</strong> Instead of putting the link in the first message, open with a short line and a
          button like “Send me the link”. When the person taps, that counts as a reply, the conversation is open, and the
          link follows. It also tells Instagram the person wanted the message, and it feels less like spam to the customer.
        </li>
        <li>
          <strong>Never make a follow the price.</strong> “Follow me first and then I&apos;ll send it” breaks Instagram&apos;s
          rules. You can invite people who don&apos;t follow you to follow, as long as they get what they asked for either way.
        </li>
      </ul>
      <p>
        Instagram also limits how fast an account can send. A post that takes off can bring hundreds of comments in an hour;
        a good tool queues the replies and sends them at a safe pace instead of firing them all at once.
      </p>

      <h2>Choosing the keyword</h2>
      <p>
        Pick a word that is short, easy to spell on a phone, and unlikely to appear by accident. “LINK” works. “Yes” does not:
        people write “yes” for all kinds of reasons. Then decide how strictly to match:
      </p>
      <ul>
        <li>
          <strong>As a word</strong> in the comment, so “send the link” and “LINK 🙏” both count, but “linked” doesn&apos;t.
        </li>
        <li>
          <strong>Exactly</strong>, when the comment must be the keyword and nothing else.
        </li>
        <li>
          <strong>Anywhere</strong> in the comment, for words that people tend to join to others.
        </li>
      </ul>
      <p>
        People rarely type exactly what you asked for, so if you ask for “PRICE”, expect “price?” and “what&apos;s the
        price” too. Matching the keyword as a word catches both. Or listen for any comment on a post where every commenter wants the
        same thing.
      </p>

      <h2>Writing the messages</h2>
      <p>
        <strong>The public reply</strong> should be short and varied. If every comment gets the identical “Check your DMs!”,
        the thread looks automated. Write three or four versions and let the tool pick one at random each time.
      </p>
      <p>
        <strong>The first DM</strong> should say who you are and what is coming, in one line: “Hi! Here&apos;s the denim jacket you
        asked about. Tap below and I&apos;ll send the link.” Then the button.
      </p>
      <p>
        <strong>The message after the tap</strong> carries the link, and one useful extra: the price, the sizes in stock, or
        how long delivery takes. End with an easy next step, such as “Reply here if you have a question about sizing.”
      </p>
      <p>Two mistakes to avoid:</p>
      <ul>
        <li>Promising something in the caption that the DM doesn&apos;t deliver, such as a discount that has expired.</li>
        <li>Turning the DM into a long menu. One link, one next step.</li>
      </ul>

      <h2>After the DM: the conversation</h2>
      <p>
        The automation starts the conversation; it doesn&apos;t finish it. Some people will ask a follow-up question within a
        minute. If nobody answers, the link alone rarely closes the sale.
      </p>
      <p>
        This is where an inbox with AI replies helps. In {N}, a follow-up question about price, size or delivery gets a reply
        drafted from your own knowledge, sent by itself on Auto (Pro) when the AI is confident, and anything else goes to a
        person. A flow can also ask for an email or phone number and save it to the contact, tag people by what they asked
        for, or wait and send a reminder, all within Instagram&apos;s 24-hour window.
      </p>

      <h2>Reading what the comments tell you</h2>
      <p>
        A busy post brings more than keyword comments. Some people ask questions, some are ready to buy, some complain, and
        some are spam. {N} reads every comment on your posts for sentiment, questions, buying signals and spam, and
        summarises each post, so you can find the comments that still need a reply. See{" "}
        <Link href="/features/comment-intelligence">comment intelligence</Link> for how that works.
      </p>

      <h2>Setting one up in {N}</h2>
      <ol>
        <li>Create an automation and pick the post or Reel, all posts, or your next post.</li>
        <li>Choose the keyword and how to match it, or any comment.</li>
        <li>Add a few public replies; one is picked at random each time.</li>
        <li>Write the first DM with a tap-first button, then the message with the link.</li>
        <li>Turn on the follow invitation if you want it. It never holds the link back.</li>
        <li>Preview it, then switch it on.</li>
      </ol>
      <p>
        Replies to your Stories and mentions of your account can start automations too. Story replies and mentions arrive as
        ordinary messages. Some other ways in, such as Live comments and chats that start from an ad, reach your account once
        Meta&apos;s approval for {N} is complete.
      </p>
      <p>
        The number of active automations depends on your plan; the <Link href="/pricing">pricing page</Link> has the
        details. If you are moving from another tool, our{" "}
        <Link href="/switch-from-manychat">guide to switching from Manychat</Link> lists what you can rebuild and what is
        different.
      </p>
    </>
  );
}

export const COMMENT_TO_DM: Guide = {
  slug: "comment-to-dm-automations",
  title: "Comment-to-DM: send the link on a keyword",
  description:
    "Set up an Instagram comment-to-DM automation that sends the link when someone comments LINK: Instagram's rules, tap-first DMs and keyword tips.",
  h1: "Comment-to-DM automations: send the link when someone comments “LINK”",
  published: "2026-10-28",
  updated: "2026-10-29",
  readingMinutes: 5,
  author: GUIDE_AUTHOR,
  tags: ["Instagram", "Automations"],
  hero: "automationPreview",
  faq: [
    {
      question: "Can I make people follow me before they get the link?",
      answer:
        "No. Instagram's rules don't allow making a follow a condition. You can invite people who don't follow you to follow, as long as they get the link either way.",
    },
    {
      question: "How many messages can I send in reply to one comment?",
      answer:
        "One private message per comment, within 7 days of the comment. Once the person replies, for example by tapping a button in that message, the usual 24-hour window opens and you can send more.",
    },
  ],
  related: [
    { label: "Comment intelligence", href: "/features/comment-intelligence" },
    { label: "Switch from Manychat", href: "/switch-from-manychat" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  Body,
};
