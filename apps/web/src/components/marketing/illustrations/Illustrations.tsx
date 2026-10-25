import { BookOpen, Lock, Mail, MessageCircle, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { cn } from "@/lib/utils";

import { LogoMark } from "../primitives";

/*
 * The feature cards' illustrations (C-068, C-138): small drawings of real screens, built from the UI
 * tokens, with made-up people and example text. Decorative: the card's heading and text say what
 * each one shows, so the box is aria-hidden.
 *
 * They are server components and always in the markup. Until C-138 they were client components
 * loaded on scroll (`dynamic(..., { ssr: false })` behind an in-view check), so the server sent
 * empty boxes and anything that did not scroll and wait (a full-page screenshot, a crawler, a slow
 * connection, a failed chunk) showed empty panels. Now the card's own entrance (`data-reveal`,
 * ScrollReveal) is the only animation; the two pulses are CSS and run only without reduced motion.
 */

// ---------------------------------------------------------------- shared pieces

const TONE = {
  brand: "bg-brand-soft text-brand-fg",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  neutral: "bg-raised text-fg-secondary",
} as const;

export function Chip({ tone = "neutral", children, className }: { tone?: keyof typeof TONE; children: ReactNode; className?: string }) {
  return <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", TONE[tone], className)}>{children}</span>;
}

export function Avatar({ initial, platform }: { initial: string; platform?: "instagram" | "whatsapp" }) {
  return (
    <span className="relative grid size-7 shrink-0 place-items-center rounded-full bg-raised text-xs font-semibold text-fg">
      {initial}
      {platform ? (
        <span
          className={cn(
            "absolute -right-0.5 -bottom-0.5 grid size-3.5 place-items-center rounded-full ring-2 ring-panel",
            platform === "instagram" ? "bg-instagram-logo-gradient" : "bg-whatsapp-logo",
          )}
        >
          <PlatformGlyph platform={platform} className="size-2 text-on-brand" />
        </span>
      ) : null}
    </span>
  );
}

/** A curve between two points of the 600 × 220 drawing, with a pulse running along it. */
function Beam({ d }: { d: string }) {
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-brand)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      <path
        d={d}
        fill="none"
        stroke="var(--color-brand-fg)"
        strokeWidth={2.5}
        strokeLinecap="round"
        pathLength={100}
        strokeDasharray="12 88"
        vectorEffect="non-scaling-stroke"
        className="motion-safe:animate-[sh-beam_2.4s_linear_infinite]"
      />
    </g>
  );
}

// ---------------------------------------------------------------- 1. an AI draft

export function DraftIllustration() {
  return (
    <div className="flex h-full flex-col justify-end gap-2.5 p-4">
      <div className="flex items-end gap-2">
        <Avatar initial="R" platform="instagram" />
        <p className="max-w-[85%] rounded-2xl rounded-bl-md border border-line-subtle bg-field px-3 py-2 text-sm">
          Is the blue kurta available in M? What&apos;s the price?
        </p>
      </div>
      <div className="flex flex-wrap gap-1.5 pl-9">
        <Chip tone="brand">Product question</Chip>
        <Chip tone="success">Lead</Chip>
      </div>
      <div className="rounded-xl border border-brand-line bg-panel p-3">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-fg" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-brand-fg">AI draft</p>
            <p className="mt-1 min-h-[2.75rem] text-sm leading-relaxed text-fg">
              Yes, the blue kurta is in stock in M. It&apos;s ₹1,499, and delivery takes 3 to 5 days. Shall I send you the order link?
            </p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 pl-5.5">
          <Chip>Price list</Chip>
          <Chip>Delivery FAQ</Chip>
          <span className="ml-auto flex gap-1.5">
            <span className="inline-flex h-7 items-center rounded-md bg-raised px-2.5 text-xs text-fg">Edit</span>
            <span className="bg-brand-gradient inline-flex h-7 items-center rounded-md px-2.5 text-xs font-medium text-on-brand">Send</span>
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 2. comment to DM, with beams

export function AutomationIllustration() {
  return (
    <div className="relative h-full min-h-56">
      <svg viewBox="0 0 600 220" preserveAspectRatio="none" className="absolute inset-0 size-full">
        <Beam d="M186,66 C231,66 231,110 276,110" />
        <Beam d="M186,154 C231,154 231,110 276,110" />
        <Beam d="M324,110 L396,110" />
      </svg>

      {[
        { top: "top-[30%]", handle: "linen.lover", initial: "L" },
        { top: "top-[70%]", handle: "weekend.wardrobe", initial: "W" },
      ].map((comment) => (
        <div key={comment.handle} className={cn("absolute left-[2%] w-[29%] -translate-y-1/2", comment.top)}>
          <div className="flex items-center gap-2 rounded-xl border border-line bg-panel px-2 py-1.5">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-raised text-xs font-semibold">{comment.initial}</span>
            <span className="min-w-0">
              <span className="block truncate text-xs text-fg-secondary">{comment.handle}</span>
              <span className="block text-sm font-semibold">LINK</span>
            </span>
          </div>
        </div>
      ))}

      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <span className="relative grid place-items-center">
          <span className="absolute inset-0 rounded-lg bg-brand motion-safe:animate-[sh-ping_2s_ease-out_infinite] motion-reduce:hidden" />
          <LogoMark className="relative size-12 shadow-glow-button" />
        </span>
      </div>

      <div className="absolute top-1/2 left-[66%] w-[32%] -translate-y-1/2">
        <div className="rounded-xl border border-line bg-panel p-2">
          <p className="flex items-center gap-1 text-xs text-fg-secondary">
            <MessageCircle className="size-3" /> Direct message
          </p>
          <p className="bg-brand-gradient mt-1.5 rounded-xl rounded-br-md px-2 py-1.5 text-xs leading-snug text-on-brand">
            Tap below and we&apos;ll send you the link.
          </p>
          <p className="mt-1.5 truncate rounded-full border border-brand-line px-2 py-1 text-center text-xs text-brand-fg">Send me the link</p>
        </div>
      </div>
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
    <div className="flex h-full flex-col justify-center gap-2 p-4">
      {ROWS.map((row) => (
        <div
          key={row.name}
          className={cn(
            "flex items-center gap-2.5 rounded-xl border px-2.5 py-2",
            row.needsYou ? "border-warning-line bg-panel" : "border-line-subtle bg-panel-glass",
          )}
        >
          <Avatar initial={row.name[0]} platform={row.platform} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{row.name}</span>
            <span className="block truncate text-xs text-fg-secondary">{row.preview}</span>
          </span>
          {row.needsYou ? <Chip tone="warning">Needs you</Chip> : null}
        </div>
      ))}
      <p className="flex items-center gap-1.5 pl-1 text-xs text-fg-secondary">
        <Sparkles className="size-3 shrink-0 text-brand-fg" /> Asked for a person, so the AI handed it to you.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- 4. knowledge gaps

export function GapsIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-2 p-4">
      <p className="flex items-center gap-1.5 text-xs font-medium text-fg-secondary">
        <BookOpen className="size-3.5" /> Questions the AI couldn&apos;t answer
      </p>
      {["Do you offer gift wrapping?", "Can I pick up from the shop?"].map((question) => (
        <div key={question} className="flex items-center gap-2 rounded-xl border border-line-subtle bg-panel px-3 py-2">
          <span className="min-w-0 flex-1 text-sm leading-snug">{question}</span>
          <span className="shrink-0 rounded-md bg-brand-soft px-2 py-1 text-xs font-medium text-brand-fg">Add answer</span>
        </div>
      ))}
      <p className="pl-1 text-xs text-fg-secondary">Not guessed: handed to you instead.</p>
    </div>
  );
}

// ---------------------------------------------------------------- 5. Ask

export function AskIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-2.5 p-4">
      <p className="bg-brand-gradient ml-auto max-w-[85%] rounded-2xl rounded-br-md px-3 py-2 text-sm text-on-brand">How did my latest Reel do?</p>
      <div className="rounded-xl border border-line bg-panel p-3">
        <p className="flex items-center gap-1.5 text-xs font-medium text-brand-fg">
          <Sparkles className="size-3.5" /> Ask
        </p>
        <p className="mt-1.5 text-sm leading-relaxed">It drew more comments than your other posts this week. Most people asked about sizes.</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Chip tone="brand">Reel, 28 Sep</Chip>
          <Chip>Comments, last 7 days</Chip>
        </div>
      </div>
      <p className="flex items-center gap-1.5 pl-1 text-xs text-fg-secondary">
        <Lock className="size-3 shrink-0" /> Read-only: it never sends or changes anything.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- 6. analytics and the digest

const BARS = [38, 52, 44, 68, 60, 82, 74];
const DAYS = ["M", "T", "W", "T", "F", "S", "S"];

export function AnalyticsIllustration() {
  return (
    <div className="grid h-full gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,15rem)]">
      <div className="flex min-w-0 flex-col">
        <p className="text-xs font-medium text-fg-secondary">Messages received, this week</p>
        <div className="mt-3 flex h-28 flex-1 items-end gap-2">
          {BARS.map((height, index) => (
            <div key={index} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
              <div className="bg-brand-gradient-decor w-full max-w-8 rounded-t-md" style={{ height: `${height}%` }} />
              <span className="text-xs text-fg-secondary">{DAYS[index]}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="hidden self-center rounded-xl border border-line bg-panel p-3 sm:block">
        <p className="flex items-center gap-1.5 text-xs text-fg-secondary">
          <Mail className="size-3.5 text-brand-fg" /> Monday, 9:00 AM
        </p>
        <p className="mt-1.5 text-sm font-semibold">Your week at Indigo Lane</p>
        <div className="mt-2 space-y-1.5">
          <span className="block h-1.5 w-full rounded-full bg-raised" />
          <span className="block h-1.5 w-4/5 rounded-full bg-raised" />
          <span className="block h-1.5 w-3/5 rounded-full bg-raised" />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the box

export const ILLUSTRATIONS = {
  draft: DraftIllustration,
  automation: AutomationIllustration,
  inbox: InboxIllustration,
  gaps: GapsIllustration,
  ask: AskIllustration,
  analytics: AnalyticsIllustration,
};

export type IllustrationName = keyof typeof ILLUSTRATIONS;

/** A feature card's picture: a fixed-height box, so nothing moves when the page loads. Decorative: aria-hidden. */
export function Illustration({ name, className }: { name: IllustrationName; className?: string }) {
  const Drawing = ILLUSTRATIONS[name];
  return (
    <div
      aria-hidden
      data-illustration={name}
      className={cn("relative h-56 overflow-hidden rounded-xl border border-line-subtle bg-canvas bg-glow-brand-top", className)}
    >
      <Drawing />
    </div>
  );
}
