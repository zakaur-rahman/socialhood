"use client";

import { BookOpen, Lock, Mail, MessageCircle, Sparkles } from "lucide-react";
import { m, useInView, useReducedMotion, type Variants } from "framer-motion";
import { useRef, type ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { cn } from "@/lib/utils";

import { DURATION, EASE_EXPRESSIVE } from "../effects/motion";
import { TextGenerateEffect } from "../effects/text-generate-effect";
import { LogoMark } from "../primitives";
import { Beam } from "./Beam";

/*
 * The feature cards' illustrations (C-068): small drawings of real screens, built from the UI
 * tokens, with made-up people and example text. Decorative: the card's heading and text say what
 * each one shows, and LazyIllustration marks the box aria-hidden. Each plays once, when it
 * scrolls into view; with reduced motion it is drawn in its final state.
 */

// ---------------------------------------------------------------- shared pieces

const RISE: Variants = {
  hidden: { opacity: 0, y: 10 },
  shown: { opacity: 1, y: 0, transition: { duration: DURATION.expressive, ease: EASE_EXPRESSIVE } },
};

const POP: Variants = {
  hidden: { opacity: 0, scale: 0.6 },
  shown: { opacity: 1, scale: 1, transition: { type: "spring", stiffness: 380, damping: 18 } },
};

/** Plays its children's variants once it is on screen, one after another. */
function Stage({ children, className, stagger = 0.18 }: { children: ReactNode; className?: string; stagger?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();
  return (
    <m.div
      ref={ref}
      className={className}
      initial={reduce ? "shown" : "hidden"}
      animate={inView || reduce ? "shown" : "hidden"}
      variants={{ hidden: {}, shown: { transition: { staggerChildren: stagger, delayChildren: 0.1 } } }}
    >
      {children}
    </m.div>
  );
}

const TONE = {
  brand: "bg-brand-soft text-brand-fg",
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  neutral: "bg-raised text-fg-secondary",
} as const;

function Chip({ tone = "neutral", children, className }: { tone?: keyof typeof TONE; children: ReactNode; className?: string }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", TONE[tone], className)}>{children}</span>;
}

function Avatar({ initial, platform }: { initial: string; platform: "instagram" | "whatsapp" }) {
  return (
    <span className="relative grid size-7 shrink-0 place-items-center rounded-full bg-raised text-xs font-semibold text-fg">
      {initial}
      <span
        className={cn(
          "absolute -right-0.5 -bottom-0.5 grid size-3.5 place-items-center rounded-full ring-2 ring-panel",
          platform === "instagram" ? "bg-instagram" : "bg-whatsapp",
        )}
      >
        <PlatformGlyph platform={platform} className="size-2 text-white" />
      </span>
    </span>
  );
}

// ---------------------------------------------------------------- 1. an AI draft, typed out

export function DraftIllustration() {
  return (
    <Stage className="flex h-full flex-col justify-end gap-2.5 p-4">
      <m.div variants={RISE} className="flex items-end gap-2">
        <Avatar initial="R" platform="instagram" />
        <p className="max-w-[85%] rounded-2xl rounded-bl-md border border-line-subtle bg-field px-3 py-2 text-sm">
          Is the blue kurta available in M? What&apos;s the price?
        </p>
      </m.div>
      <m.div variants={RISE} className="flex flex-wrap gap-1.5 pl-9">
        <Chip tone="brand">Product question</Chip>
        <Chip tone="success">Lead</Chip>
      </m.div>
      <m.div variants={RISE} className="rounded-xl border border-brand-line bg-panel p-3">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-fg" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-brand-fg">AI draft</p>
            <TextGenerateEffect
              words="Yes, the blue kurta is in stock in M. It's ₹1,499, and delivery takes 3 to 5 days. Shall I send you the order link?"
              className="mt-1 min-h-[2.75rem] text-sm leading-relaxed text-fg"
              stagger={0.07}
            />
          </div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 pl-5.5">
          <Chip>Price list</Chip>
          <Chip>Delivery FAQ</Chip>
          <span className="ml-auto flex gap-1.5">
            <span className="inline-flex h-7 items-center rounded-md bg-raised px-2.5 text-xs text-fg">Edit</span>
            <span className="bg-brand-gradient inline-flex h-7 items-center rounded-md px-2.5 text-xs font-medium text-white">Send</span>
          </span>
        </div>
      </m.div>
    </Stage>
  );
}

// ---------------------------------------------------------------- 2. comment → DM, with beams

export function AutomationIllustration() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();
  const shown = inView || Boolean(reduce);
  return (
    <div ref={ref} className="relative h-full min-h-56">
      <svg viewBox="0 0 600 220" preserveAspectRatio="none" className="absolute inset-0 size-full">
        <Beam d="M186,66 C231,66 231,110 276,110" active={shown} />
        <Beam d="M186,154 C231,154 231,110 276,110" active={shown} delay={0.15} />
        <Beam d="M324,110 L396,110" active={shown} delay={0.9} />
      </svg>

      {[
        { top: "top-[30%]", handle: "linen.lover", initial: "L" },
        { top: "top-[70%]", handle: "weekend.wardrobe", initial: "W" },
      ].map((comment, index) => (
        <m.div
          key={comment.handle}
          className={cn("absolute left-[2%] w-[29%] -translate-y-1/2", comment.top)}
          initial={reduce ? false : { opacity: 0, x: -8 }}
          animate={shown ? { opacity: 1, x: 0 } : undefined}
          transition={{ duration: DURATION.expressive, ease: EASE_EXPRESSIVE, delay: index * 0.15 }}
        >
          <div className="flex items-center gap-2 rounded-xl border border-line bg-panel px-2 py-1.5">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-raised text-xs font-semibold">{comment.initial}</span>
            <span className="min-w-0">
              <span className="block truncate text-xs text-fg-secondary">{comment.handle}</span>
              <span className="block text-sm font-semibold">LINK</span>
            </span>
          </div>
        </m.div>
      ))}

      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <span className="relative grid place-items-center">
          {shown && !reduce ? (
            <span className="absolute inset-0 rounded-[10px] bg-brand motion-safe:animate-[sh-ping_2s_ease-out_infinite]" />
          ) : null}
          <LogoMark className="relative size-12 shadow-lg shadow-brand/30" />
        </span>
      </div>

      <m.div
        className="absolute top-1/2 left-[66%] w-[32%] -translate-y-1/2"
        initial={reduce ? false : { opacity: 0, x: 8 }}
        animate={shown ? { opacity: 1, x: 0 } : undefined}
        transition={{ duration: DURATION.expressive, ease: EASE_EXPRESSIVE, delay: 1.3 }}
      >
        <div className="rounded-xl border border-line bg-panel p-2">
          <p className="flex items-center gap-1 text-xs text-fg-secondary">
            <MessageCircle className="size-3" /> Direct message
          </p>
          <p className="bg-brand-gradient mt-1.5 rounded-xl rounded-br-md px-2 py-1.5 text-xs leading-snug text-white">
            Tap below and we&apos;ll send you the link.
          </p>
          <p className="mt-1.5 truncate rounded-full border border-brand-line px-2 py-1 text-center text-xs text-brand-fg">Send me the link</p>
        </div>
      </m.div>
    </div>
  );
}

// ---------------------------------------------------------------- 3. the inbox and "Needs you"

const ROWS = [
  { name: "Arjun P.", preview: "Do you deliver to Pune?", platform: "instagram" as const },
  { name: "Neha D.", preview: "Can I talk to a person, please?", platform: "whatsapp" as const, needsYou: true },
  { name: "Sana M.", preview: "What time do you open on Sunday?", platform: "instagram" as const },
];

export function InboxIllustration() {
  return (
    <Stage className="flex h-full flex-col justify-center gap-2 p-4" stagger={0.14}>
      {ROWS.map((row) => (
        <m.div
          key={row.name}
          variants={RISE}
          className={cn(
            "flex items-center gap-2.5 rounded-xl border px-2.5 py-2",
            row.needsYou ? "border-warning/40 bg-panel" : "border-line-subtle bg-panel/60",
          )}
        >
          <Avatar initial={row.name[0]} platform={row.platform} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{row.name}</span>
            <span className="block truncate text-xs text-fg-secondary">{row.preview}</span>
          </span>
          {row.needsYou ? (
            <m.span variants={POP} className="shrink-0">
              <Chip tone="warning">Needs you</Chip>
            </m.span>
          ) : null}
        </m.div>
      ))}
      <m.p variants={RISE} className="flex items-center gap-1.5 pl-1 text-xs text-fg-secondary">
        <Sparkles className="size-3 text-brand-fg" /> Asked for a person, so the AI handed it to you.
      </m.p>
    </Stage>
  );
}

// ---------------------------------------------------------------- 4. knowledge gaps

export function GapsIllustration() {
  return (
    <Stage className="flex h-full flex-col justify-center gap-2 p-4" stagger={0.16}>
      <m.p variants={RISE} className="flex items-center gap-1.5 text-xs font-medium text-fg-secondary">
        <BookOpen className="size-3.5" /> Questions the AI couldn&apos;t answer
      </m.p>
      {["Do you offer gift wrapping?", "Can I pick up from the shop?"].map((question) => (
        <m.div key={question} variants={RISE} className="flex items-center gap-2 rounded-xl border border-line-subtle bg-panel px-3 py-2">
          <span className="min-w-0 flex-1 text-sm leading-snug">{question}</span>
          <span className="shrink-0 rounded-md bg-brand-soft px-2 py-1 text-xs font-medium text-brand-fg">Add answer</span>
        </m.div>
      ))}
      <m.p variants={RISE} className="pl-1 text-xs text-fg-secondary">
        Not guessed: handed to you instead.
      </m.p>
    </Stage>
  );
}

// ---------------------------------------------------------------- 5. Ask Social Hood

export function AskIllustration() {
  return (
    <Stage className="flex h-full flex-col justify-center gap-2.5 p-4" stagger={0.22}>
      <m.p variants={RISE} className="bg-brand-gradient ml-auto max-w-[85%] rounded-2xl rounded-br-md px-3 py-2 text-sm text-white">
        How did my latest Reel do?
      </m.p>
      <m.div variants={RISE} className="rounded-xl border border-line bg-panel p-3">
        <p className="flex items-center gap-1.5 text-xs font-medium text-brand-fg">
          <Sparkles className="size-3.5" /> Ask Social Hood
        </p>
        <p className="mt-1.5 text-sm leading-relaxed">It drew more comments than your other posts this week. Most people asked about sizes.</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Chip tone="brand">Reel, 28 Sep</Chip>
          <Chip>Comments, last 7 days</Chip>
        </div>
      </m.div>
      <m.p variants={RISE} className="flex items-center gap-1.5 pl-1 text-xs text-fg-secondary">
        <Lock className="size-3" /> Read-only: it never sends or changes anything.
      </m.p>
    </Stage>
  );
}

// ---------------------------------------------------------------- 6. analytics and the digest

const BARS = [38, 52, 44, 68, 60, 82, 74];
const DAYS = ["M", "T", "W", "T", "F", "S", "S"];

export function AnalyticsIllustration() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const reduce = useReducedMotion();
  const shown = inView || Boolean(reduce);
  return (
    <div ref={ref} className="grid h-full gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,15rem)]">
      <div className="flex min-w-0 flex-col">
        <p className="text-xs font-medium text-fg-secondary">Messages received, this week</p>
        <div className="mt-3 flex h-28 flex-1 items-end gap-2">
          {BARS.map((height, index) => (
            <div key={index} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
              <m.div
                className="bg-brand-gradient-decor w-full max-w-8 origin-bottom rounded-t-md"
                style={{ height: `${height}%` }}
                initial={reduce ? false : { scaleY: 0 }}
                animate={shown ? { scaleY: 1 } : undefined}
                transition={{ duration: 0.6, ease: EASE_EXPRESSIVE, delay: index * 0.06 }}
              />
              <span className="text-xs text-fg-secondary">{DAYS[index]}</span>
            </div>
          ))}
        </div>
      </div>
      <m.div
        className="hidden self-center rounded-xl border border-line bg-panel p-3 sm:block"
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={shown ? { opacity: 1, y: 0 } : undefined}
        transition={{ duration: DURATION.expressive, ease: EASE_EXPRESSIVE, delay: 0.6 }}
      >
        <p className="flex items-center gap-1.5 text-xs text-fg-secondary">
          <Mail className="size-3.5 text-brand-fg" /> Monday, 9:00 AM
        </p>
        <p className="mt-1.5 text-sm font-semibold">Your week at Indigo Lane</p>
        <div className="mt-2 space-y-1.5">
          <span className="block h-1.5 w-full rounded-full bg-raised" />
          <span className="block h-1.5 w-4/5 rounded-full bg-raised" />
          <span className="block h-1.5 w-3/5 rounded-full bg-raised" />
        </div>
      </m.div>
    </div>
  );
}
