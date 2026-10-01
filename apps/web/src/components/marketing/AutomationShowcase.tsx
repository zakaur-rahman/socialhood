import { Hand, Link2, MessageCircle, MessageSquareReply } from "lucide-react";
import Image from "next/image";
import type { CSSProperties } from "react";

import { TraceLine } from "./effects/TraceLine";
import { Container } from "./primitives";
import { SHOTS } from "./shots";

// FR-AUT-21 tap first and FR-AUT-22 the follow nudge, as the product guide describes them.
const STEPS = [
  {
    icon: MessageCircle,
    title: "Someone comments LINK",
    body: "On any post or Reel, or only the ones you choose. The keyword is yours: LINK, PRICE, anything.",
  },
  {
    icon: MessageSquareReply,
    title: "A public reply, if you want one",
    body: "“Sent you a DM!” under their comment, so everyone sees you answered.",
  },
  {
    icon: Hand,
    title: "Tap first",
    body: "The DM opens with a button like “Send me the link”, and the link follows their tap. It works better with Instagram and feels less spammy.",
  },
  {
    icon: Link2,
    title: "The link, and a polite follow nudge",
    body: "They always get what they asked for. People who don't follow you can get a friendly invitation to follow, never a condition for getting the link.",
  },
];

/** "Comment LINK, get the link in a DM": the steps with a rail that draws itself, beside the editor's real preview. */
export function AutomationShowcase() {
  return (
    <section aria-labelledby="showcase-title" className="relative overflow-hidden py-20 sm:py-24">
      <div
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-0 h-[32rem] w-[32rem] -translate-y-1/2 translate-x-1/3 rounded-full bg-[radial-gradient(closest-side,var(--color-brand-soft),transparent)]"
      />
      <Container className="relative grid items-center gap-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)] lg:gap-20">
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-brand-fg uppercase">Automations</p>
          <h2 id="showcase-title" className="mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Comment LINK, get the link in a DM
          </h2>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-pretty text-fg-secondary">
            Turn comments into conversations, the way Instagram allows. Replies are queued to stay within Instagram&apos;s
            sending limits, so a busy post is handled safely.
          </p>
          <div className="relative mt-10">
            <TraceLine className="top-5 bottom-5 left-[1.1875rem]" />
            <ol className="relative space-y-6">
              {STEPS.map(({ icon: Icon, title, body }, index) => (
                <li
                  key={title}
                  data-reveal
                  style={{ "--reveal-delay": `${index * 150}ms` } as CSSProperties}
                  className="relative flex gap-4"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-full border border-brand-line bg-panel text-brand-fg ring-4 ring-canvas">
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <div className="min-w-0 pt-1.5">
                    <h3 className="text-base font-semibold">
                      <span className="sr-only">Step {index + 1}:</span>{" "}
                      {title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-fg-secondary">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <figure data-reveal className="mx-auto w-full max-w-sm">
          <div className="rounded-2xl border border-line-strong bg-panel p-2 shadow-2xl shadow-brand/15">
            <Image
              src={SHOTS.automationPreview.src}
              width={SHOTS.automationPreview.width}
              height={SHOTS.automationPreview.height}
              alt={SHOTS.automationPreview.alt}
              sizes="(min-width: 1024px) 22rem, (min-width: 640px) 24rem, calc(100vw - 3rem)"
              className="h-auto w-full rounded-xl"
            />
          </div>
          <figcaption className="mt-3 text-center text-xs text-fg-secondary">
            The automation editor&apos;s live preview, with example text.
          </figcaption>
        </figure>
      </Container>
    </section>
  );
}
