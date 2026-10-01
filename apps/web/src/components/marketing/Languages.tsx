import { Sparkles } from "lucide-react";
import type { CSSProperties } from "react";

import { Container, SectionHeading } from "./primitives";

type Example = { language: string; lang: string; question: string; reply: string };

// Example conversations for a made-up clothing shop. The AI answers in the customer's language
// from the shop's own knowledge (product guide: English, Hindi and Hinglish).
const EXAMPLES: Example[] = [
  {
    language: "English",
    lang: "en",
    question: "Do you deliver to Pune? How long does it take?",
    reply: "Yes, we deliver across India. Orders ship within 2 working days and arrive in 3 to 5 days. Shall I send you the order link?",
  },
  {
    language: "Hindi",
    lang: "hi",
    question: "क्या यह कुर्ता M साइज़ में मिलेगा?",
    reply: "जी हाँ, यह कुर्ता M साइज़ में उपलब्ध है। क्या मैं आपको ऑर्डर का लिंक भेज दूँ?",
  },
  {
    language: "Hinglish",
    lang: "hi-Latn",
    question: "Return ho sakta hai kya agar size fit na ho?",
    reply: "Haan, delivery ke 7 din ke andar return ya exchange ho jaata hai, bas tags lage hone chahiye.",
  },
];

/** The AI's three languages, as replies to real-sounding questions (examples, labelled as such). */
export function Languages() {
  return (
    <section aria-labelledby="languages-title" className="border-t border-line-subtle bg-panel/30 py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="languages-title"
          eyebrow="Languages"
          title="Replies in English, Hindi and Hinglish"
          intro="The AI understands your customers and answers in their language, from your own knowledge."
        />
        <ul className="mx-auto mt-14 grid max-w-5xl gap-4 md:grid-cols-3">
          {EXAMPLES.map((example, index) => (
            <li key={example.language} data-reveal style={{ "--reveal-delay": `${index * 100}ms` } as CSSProperties}>
              <article
                aria-labelledby={`language-${example.lang}`}
                className="group flex h-full flex-col gap-3 rounded-2xl border border-line bg-canvas p-5 transition-[border-color,box-shadow,translate] duration-200 hover:border-brand-line hover:shadow-xl hover:shadow-brand/10 motion-safe:hover:-translate-y-1"
              >
                <h3 id={`language-${example.lang}`} className="text-xs font-semibold tracking-[0.14em] text-fg-secondary uppercase">
                  {example.language}
                </h3>
                <p className="max-w-[90%] rounded-2xl rounded-bl-md border border-line-subtle bg-field px-3 py-2 text-sm leading-relaxed">
                  <span className="sr-only">Customer: </span>
                  <span lang={example.lang}>{example.question}</span>
                </p>
                <div className="bg-brand-gradient ml-auto max-w-[90%] rounded-2xl rounded-br-md px-3 py-2 text-sm leading-relaxed text-white">
                  <p className="flex items-center gap-1 text-xs font-medium text-white" aria-hidden>
                    <Sparkles className="size-3" /> AI reply
                  </p>
                  <p className="mt-1">
                    <span className="sr-only">AI reply: </span>
                    <span lang={example.lang}>{example.reply}</span>
                  </p>
                </div>
              </article>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-center text-xs text-fg-secondary">
          Example replies for a made-up shop. Yours use your own prices, policies and tone.
        </p>
      </Container>
    </section>
  );
}
