import { ArrowRight, Sparkles } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { Container, CtaLink, MARKETING_CARD, SECTION_EYEBROW } from "@/components/marketing/primitives";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";
import { guidePath } from "@/lib/marketing/guides";
import { LANDING_LANGUAGES, pageMetadata } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, SITE_NAME, appUrl } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";
import { EYEBROW, MARKETING_HEADING } from "@/styles/tokens";

/** The page's path; the landing page names it as its Hindi alternate (LANDING_LANGUAGES). */
const PATH = LANDING_LANGUAGES.hi;

export const metadata = pageMetadata({
  title: "Instagram aur WhatsApp ke liye AI inbox",
  description: `Instagram DMs, comments aur WhatsApp ek inbox mein. ${SITE_NAME} ka AI aapki knowledge se English, Hindi ya Hinglish mein reply likhta hai.`,
  path: PATH,
  languages: { ...LANDING_LANGUAGES },
  locale: "hi_IN",
});

// C-153: the product in Hinglish (Hindi in Latin letters, as many Indian sellers type), short and
// plain. Every claim is one the English pages make (C-122, C-138). A native speaker should review
// the copy before launch.
const FEATURES = [
  {
    title: "Sab messages ek jagah",
    body: "Instagram DMs, comments aur WhatsApp chats ek hi inbox mein. Team ke saath kaam karein: conversation assign karein, saved replies use karein.",
  },
  {
    title: "AI reply, aapki apni knowledge se",
    body: "Aap apne products, prices aur policies daalte hain. AI sirf unhi se jawab likhta hai. Jawab nahi pata toh guess nahi karta, conversation aapko de deta hai.",
  },
  {
    title: "Customer ki bhasha mein",
    body: "Customer ne English, Hindi ya Hinglish mein likha ho, reply usi bhasha mein banta hai. Knowledge ek baar English ya Hindi mein likhna kaafi hai.",
  },
  {
    title: "Control aapke haath mein",
    body: "Har account ke liye Off, Suggest ya Auto. Suggest mein AI draft likhta hai aur aap bhejte hain. Auto mein confident hone par AI khud bhejta hai; Auto Pro plan mein hai.",
  },
  {
    title: "Comment pe LINK, DM mein link",
    body: "Koi post pe “LINK” likhe, toh use DM mein link chala jaata hai. Follow karne ki shart nahi lagti, kyunki Instagram ke rules ise allow nahi karte.",
  },
  {
    title: "Mushkil messages aapke paas",
    body: "Refund, complaint, legal baat ya jo AI ko pakka na pata ho, woh “Needs you” mein jaata hai. Aap khud reply karein toh AI us chat mein ruk jaata hai.",
  },
];

const KNOW = [
  `Instagram aur WhatsApp connect karna Meta ke ${SITE_NAME} app ko approve karne par depend karta hai.`,
  "Instagram pe business customer ke last message ke 24 ghante ke andar hi reply kar sakta hai.",
  "WhatsApp ki messaging fees Meta seedha aapke business se leta hai. Hamare plans mein yeh shaamil nahi hai.",
  "AI English, Hindi aur Hinglish samajhta hai. Baaki Indian bhashayein abhi support nahi hain.",
  "Free plan ke liye card nahi chahiye. Plans aur limits pricing page pe hain (English mein).",
];

const LINK = "font-medium text-brand-fg underline-offset-4 hover:underline";

/** /hi (C-153): the landing page's Hinglish version, with hreflang both ways. Static. */
export default function HinglishPage() {
  return (
    <main id="main" tabIndex={-1} lang="hi-Latn" className="flex-1 outline-none">
      <BreadcrumbJsonLd name="Hinglish" path={PATH} />
      <section className="py-16 sm:py-20">
        <Container className="max-w-3xl">
          <p className={SECTION_EYEBROW}>{SITE_NAME} Hinglish mein</p>
          <h1 className={cn(MARKETING_HEADING, "mt-3 text-balance sm:text-5xl")}>
            Instagram aur WhatsApp ke customers ko jaldi jawab, apni bhasha mein
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-pretty text-fg-secondary">
            {SITE_NAME} aapke Instagram DMs, comments aur WhatsApp chats ek inbox mein laata hai. AI aapki business knowledge
            se reply likhta hai, aur jo baat use nahi pata, woh aapko bata deta hai.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="w-full px-6 sm:w-auto">
              Free mein shuru karein <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href={PRICING_PATH} variant="secondary" className="w-full px-6 sm:w-auto">
              Plans aur limits dekhein
            </CtaLink>
          </div>
          <p className="mt-6 text-sm">
            <Link href="/" lang="en" hrefLang="en" className={cn(LINK, "inline-flex min-h-10 items-center")}>
              Read this in English
            </Link>
          </p>
        </Container>
      </section>

      <section aria-labelledby="hi-features-title" className="border-t border-line-subtle py-14 sm:py-16">
        <Container>
          <h2 id="hi-features-title" className="text-2xl font-semibold tracking-tight">
            Kya kya milta hai
          </h2>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((item) => (
              <li key={item.title} className={cn(MARKETING_CARD, "p-5")}>
                <h3 className="text-base font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{item.body}</p>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      <section aria-labelledby="hi-example-title" className="border-t border-line-subtle py-14 sm:py-16">
        <Container className="max-w-3xl">
          <h2 id="hi-example-title" className="text-2xl font-semibold tracking-tight">
            Ek example
          </h2>
          <div className={cn(MARKETING_CARD, "mt-6 flex flex-col gap-3 p-5")}>
            <p className={EYEBROW}>Instagram DM</p>
            <p className="max-w-[90%] rounded-2xl rounded-bl-md border border-line-subtle bg-field px-3 py-2 text-sm leading-relaxed">
              <span className="sr-only">Customer: </span>
              Return ho sakta hai kya agar size fit na ho?
            </p>
            <div className="bg-brand-gradient ml-auto max-w-[90%] rounded-2xl rounded-br-md px-3 py-2 text-sm leading-relaxed text-on-brand">
              <p className="flex items-center gap-1 text-xs font-medium" aria-hidden>
                <Sparkles className="size-3" /> AI reply
              </p>
              <p className="mt-1">
                <span className="sr-only">AI reply: </span>
                Haan, delivery ke 7 din ke andar return ya exchange ho jaata hai, bas tags lage hone chahiye.
              </p>
            </div>
          </div>
          <p className="mt-3 text-xs text-fg-secondary">
            Yeh ek banayi hui dukaan ka example hai. Aapke replies aapki apni policy aur tone se bante hain.
          </p>
        </Container>
      </section>

      <section aria-labelledby="hi-know-title" className="border-t border-line-subtle py-14 sm:py-16">
        <Container className="max-w-3xl">
          <h2 id="hi-know-title" className="text-2xl font-semibold tracking-tight">
            Shuru karne se pehle jaan lein
          </h2>
          <ul className="mt-6 list-disc space-y-3 pl-5 text-sm leading-relaxed text-fg-secondary">
            {KNOW.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="mt-8 text-sm text-fg-secondary">
            Hinglish replies ke baare mein detail mein padhna hai?{" "}
            <Link href={guidePath("replying-in-hinglish") as Route} lang="en" hrefLang="en" className={LINK}>
              Replying in Hinglish: how AI handles mixed messages
            </Link>{" "}
            (English mein).
          </p>
          <div className="mt-8">
            <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="w-full px-6 sm:w-auto">
              Free mein shuru karein
            </CtaLink>
          </div>
        </Container>
      </section>
    </main>
  );
}
