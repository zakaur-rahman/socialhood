"use client";

import { useInView } from "framer-motion";
import dynamic from "next/dynamic";
import { useRef } from "react";

import { cn } from "@/lib/utils";

const load = () => import("./Illustrations");

// One chunk for all six, fetched when the first card comes near the screen.
const ILLUSTRATIONS = {
  draft: dynamic(() => load().then((module) => module.DraftIllustration), { ssr: false }),
  automation: dynamic(() => load().then((module) => module.AutomationIllustration), { ssr: false }),
  inbox: dynamic(() => load().then((module) => module.InboxIllustration), { ssr: false }),
  gaps: dynamic(() => load().then((module) => module.GapsIllustration), { ssr: false }),
  ask: dynamic(() => load().then((module) => module.AskIllustration), { ssr: false }),
  analytics: dynamic(() => load().then((module) => module.AnalyticsIllustration), { ssr: false }),
};

export type IllustrationName = keyof typeof ILLUSTRATIONS;

/**
 * A feature card's illustration, loaded when the card is within 400 px of the screen (C-068).
 * The box has a fixed height, so the page doesn't move when it arrives. Decorative: aria-hidden.
 */
export function LazyIllustration({ name, className }: { name: IllustrationName; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const near = useInView(ref, { once: true, margin: "400px 0px" });
  const Illustration = ILLUSTRATIONS[name];
  return (
    <div
      ref={ref}
      aria-hidden
      data-illustration={name}
      className={cn(
        "relative h-56 overflow-hidden rounded-xl border border-line-subtle bg-canvas bg-[radial-gradient(120%_80%_at_50%_0%,var(--color-brand-soft),transparent_60%)]",
        className,
      )}
    >
      {near ? <Illustration /> : null}
    </div>
  );
}
