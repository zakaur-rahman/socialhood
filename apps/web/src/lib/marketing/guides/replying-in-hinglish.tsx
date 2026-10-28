import Link from "next/link";
import type { ReactNode } from "react";

import { SITE_NAME } from "../site";
import { GUIDE_AUTHOR, type Guide } from "./types";

const N = SITE_NAME;

/** A customer's or a reply's words, marked as Hinglish for screen readers and search. */
function Hi({ children }: { children: ReactNode }) {
  return <span lang="hi-Latn">{children}</span>;
}

function Body() {
  return (
    <>
      <p>
        Open the DMs of almost any Indian shop on Instagram or WhatsApp and you will find messages like these:{" "}
        <Hi>“Ye kurta M size mein milega?”</Hi>, <Hi>“COD available hai kya?”</Hi>, <Hi>“bhai price batao”</Hi>. This is
        Hinglish: Hindi written in English letters, mixed freely with English words. For many customers it is simply how they
        type.
      </p>
      <p>
        If you reply by hand, you switch without thinking. If software replies for you, it has to understand the mix and
        answer in kind, or the conversation suddenly feels like it is happening with a form. This guide explains what makes
        Hinglish hard for software, how a modern AI handles it, and how to set things up so replies sound natural.
      </p>

      <h2>Why Hinglish trips up older tools</h2>
      <p>Keyword bots and older chat tools struggle with Hinglish for a few reasons:</p>
      <ul>
        <li>
          <strong>No fixed spelling.</strong> The same word appears as <Hi>“nahi”</Hi>, <Hi>“nahin”</Hi> and{" "}
          <Hi>“nhi”</Hi>; <Hi>“hai”</Hi> as <Hi>“h”</Hi> or <Hi>“he”</Hi>. A bot that looks for exact words misses most of
          them.
        </li>
        <li>
          <strong>Two languages in one sentence.</strong> <Hi>“Delivery kab tak hogi Pune mein?”</Hi> has English nouns,
          Hindi grammar and a city name. Translating word by word gives nonsense.
        </li>
        <li>
          <strong>Short forms and politeness.</strong> <Hi>“plz”</Hi>, <Hi>“bhai”</Hi>, <Hi>“ji”</Hi> and{" "}
          <Hi>“sir”</Hi> carry tone, not information, but a reply that ignores the tone feels cold.
        </li>
        <li>
          <strong>Script switching.</strong> The same customer might write one message in Devanagari and the next in Latin
          letters.
        </li>
      </ul>

      <h2>How a modern AI reads mixed messages</h2>
      <p>
        Large language models learn from huge amounts of real text, and a lot of the Indian internet is written in Hinglish.
        So unlike a keyword bot, they read <Hi>“kitne ka hai”</Hi> and “what&apos;s the price” as the same question, whatever
        the spelling. That solves understanding. A good reply needs two more things: answering in the right language, and
        answering with the right facts.
      </p>

      <h2>How {N} handles it</h2>
      <h3>It notes the language of every message</h3>
      <p>
        When a message arrives, {N}&apos;s AI reads it for intent, sentiment and language. Hindi written in English letters
        is marked as its own case, separate from Hindi in Devanagari and from English, because the reply should match what
        the customer typed, not just the language underneath.
      </p>
      <h3>It replies in the customer&apos;s language</h3>
      <p>
        The draft reply follows the customer: English for English, Hindi in Devanagari for Hindi, and Hinglish in English
        letters for Hinglish. You don&apos;t need to keep three versions of your knowledge. Write your prices, policies and
        answers once, in English or Hindi, and the AI answers a Hinglish question in Hinglish from those facts.
      </p>
      <p>For example, with a return policy written in English in your knowledge:</p>
      <ul>
        <li>
          Customer: <Hi>“Return ho sakta hai kya agar size fit na ho?”</Hi>
        </li>
        <li>
          Reply: <Hi>“Haan, delivery ke 7 din ke andar return ya exchange ho jaata hai, bas tags lage hone chahiye.”</Hi>
        </li>
      </ul>
      <p>That is an example for a made-up shop; your replies use your own policy and tone.</p>
      <h3>The facts still come only from you</h3>
      <p>
        Switching language doesn&apos;t loosen the rules. The AI answers only from your knowledge and the conversation. If a
        customer asks <Hi>“Dubai bhejte ho?”</Hi> and you have never written down whether you ship abroad, the AI
        doesn&apos;t guess: the conversation goes to you, and the question is recorded as a knowledge gap so you can add the
        answer once.
      </p>
      <h3>Product questions find the product</h3>
      <p>
        When you add a product catalogue, a question like <Hi>“blue kurta kitne ka hai?”</Hi> is matched to your “Blue
        kurta” listing. Common Hinglish filler words such as <Hi>“kitne”</Hi>, <Hi>“ka”</Hi>, <Hi>“hai”</Hi> and{" "}
        <Hi>“chahiye”</Hi> are ignored when matching, so the product name does the work, and the reply quotes the price and
        stock exactly as you listed them.
      </p>
      <h3>Small talk gets a small reply</h3>
      <p>
        Not every message is a question. <Hi>“Namaste”</Hi>, <Hi>“kaise ho”</Hi> and <Hi>“shukriya”</Hi> get a short,
        friendly reply in the same language, with no business facts in it, instead of “Sorry, I don&apos;t know that”.
      </p>
      <h3>Your own replies stay in your words</h3>
      <p>
        When you type a reply yourself, AI Polish can fix spelling and clarity before you send it. It keeps your language
        and script: a Hinglish reply stays Hinglish in English letters and is never translated, and it doesn&apos;t add
        facts, prices or promises you didn&apos;t write.
      </p>

      <h2>Setting it up well</h2>
      <ol>
        <li>
          <strong>Write your knowledge plainly.</strong> English or Hindi both work. Short, clear facts beat long paragraphs:
          “Delivery takes 3 to 5 days in metro cities, 5 to 8 days elsewhere” is easy to answer from in any language.
        </li>
        <li>
          <strong>Add the questions people really ask.</strong> In your questions and answers, write the question the way
          customers type it, Hinglish included. It helps the AI connect the question to the answer.
        </li>
        <li>
          <strong>Set your voice.</strong> Choose a tone and whether you use emoji in the brand voice settings, and list
          words to always or never use. These apply in every language.
        </li>
        <li>
          <strong>Start on Suggest.</strong> Read the Hinglish drafts for a week before you let anything send by itself.
          If a reply reads stiffly, change the voice settings or the knowledge rather than fixing each draft by hand.
        </li>
      </ol>

      <h2>What to expect, honestly</h2>
      <ul>
        <li>
          The AI supports English, Hindi and Hinglish. Other Indian languages, such as Tamil, Bengali or Marathi, are not
          supported yet.
        </li>
        <li>
          A message that is almost all English, with one Hindi word, may get an English reply. That is usually what the
          customer expects, but check the drafts while you are on Suggest.
        </li>
        <li>
          Hinglish has no standard spelling, so replies use common spellings. They may not match your own habits exactly;
          AI Polish and your edits keep your own messages in your style.
        </li>
        <li>
          Automatic sending (Auto) is part of the Pro plan. On Free, the AI suggests replies and you send them.
        </li>
      </ul>
      <p>
        See the <Link href="/features/ai-inbox">AI inbox page</Link> for how drafts, Auto and the hand-off to a person work
        together, our guide to <Link href="/guides/instagram-dm-auto-replies">auto-replies that don&apos;t sound like a bot</Link>,
        and the <Link href="/pricing">pricing page</Link> for what each plan includes. This page is also available{" "}
        <Link href="/hi">
          <Hi>Hinglish mein</Hi>
        </Link>
        .
      </p>
    </>
  );
}

export const REPLYING_IN_HINGLISH: Guide = {
  slug: "replying-in-hinglish",
  title: "How AI replies to Hinglish customer messages",
  description:
    "How AI understands mixed Hindi and English customer messages and replies in Hinglish from your own facts, with setup tips for Indian sellers.",
  h1: "Replying in Hinglish: how AI handles mixed Hindi and English customer messages",
  published: "2026-10-28",
  updated: "2026-10-28",
  readingMinutes: 5,
  author: GUIDE_AUTHOR,
  tags: ["AI replies", "Hindi and Hinglish"],
  faq: [
    {
      question: "Do I need to write my knowledge base in Hinglish?",
      answer:
        "No. Write it once in English or Hindi. The AI answers a Hinglish question in Hinglish from those facts, and only from them.",
    },
    {
      question: "Which languages does the AI reply in?",
      answer: "English, Hindi and Hinglish, following the language of the customer's message.",
    },
  ],
  related: [
    { label: "The AI inbox", href: "/features/ai-inbox" },
    { label: `${N} Hinglish mein`, href: "/hi", lang: "hi-Latn" },
    { label: "Plans and limits", href: "/pricing" },
  ],
  Body,
};
