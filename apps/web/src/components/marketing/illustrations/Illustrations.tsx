import { CalendarDays, Check, Lock, Mail, MessageCircle, ShieldCheck, Sparkles, UserRound } from "lucide-react";
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
    <>
      {/* Phones: the same story, stacked (the drawing below needs about 30 rem). */}
      <div className="flex h-full flex-col justify-center gap-2 p-4 sm:hidden">
        <div className="flex gap-2">
          {["linen.lover", "weekend.wardrobe"].map((handle) => (
            <div key={handle} className="min-w-0 flex-1 rounded-xl border border-line bg-panel px-2 py-1.5">
              <span className="block truncate text-xs text-fg-secondary">{handle}</span>
              <span className="block text-sm font-semibold">LINK</span>
            </div>
          ))}
        </div>
        <p className="flex items-center justify-center gap-1.5 text-xs text-brand-fg">
          <LogoMark className="size-5" /> sends a DM to each
        </p>
        <div className="rounded-xl border border-line bg-panel p-2">
          <p className="bg-brand-gradient rounded-xl rounded-br-md px-2 py-1.5 text-xs leading-snug text-on-brand">Tap below and we&apos;ll send you the link.</p>
          <p className="mt-1.5 rounded-full border border-brand-line px-2 py-1 text-center text-xs text-brand-fg">Send me the link</p>
        </div>
      </div>
    <div className="relative hidden h-full min-h-56 sm:block">
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
    </>
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
    <div className="flex h-full flex-col justify-center gap-3 p-4">
      <div className="flex min-w-0 flex-col">
        <p className="text-xs font-medium text-fg-secondary">Messages received, this week</p>
        <div className="mt-3 flex h-24 items-end gap-2">
          {BARS.map((height, index) => (
            <div key={index} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
              <div className="bg-brand-gradient-decor w-full max-w-8 rounded-t-md" style={{ height: `${height}%` }} />
              <span className="text-xs text-fg-secondary">{DAYS[index]}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2 rounded-xl border border-line bg-panel px-3 py-2">
        <Mail className="size-3.5 shrink-0 text-brand-fg" />
        <span className="min-w-0 flex-1 truncate text-sm font-semibold">Your week at Indigo Lane</span>
        <span className="shrink-0 text-xs text-fg-secondary">Mon, 9:00 AM</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 7. comment intelligence

const SENTIMENT = [
  { label: "Positive", width: "w-[62%]", bar: "bg-success" },
  { label: "Neutral", width: "w-[26%]", bar: "bg-line-strong" },
  { label: "Negative", width: "w-[12%]", bar: "bg-danger" },
];

export function CommentsIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-2.5 p-4">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-medium text-fg-secondary">Linen shirt Reel · 48 comments</span>
        <span className="flex gap-1.5">
          <Chip tone="brand">Price 12</Chip>
          <Chip>Size 9</Chip>
        </span>
      </div>
      <div className="flex h-2 gap-0.5 overflow-hidden rounded-full">
        {SENTIMENT.map((part) => (
          <span key={part.label} className={cn("h-full", part.width, part.bar)} />
        ))}
      </div>
      {[
        { who: "R", text: "Love this colour! What does it cost?", chips: <Chip tone="success">Positive</Chip>, action: "Reply by DM" },
        { who: "K", text: "Follow my page for free followers", chips: <Chip tone="warning">Spam</Chip>, action: "Hidden" },
      ].map((comment) => (
        <div key={comment.who} className="flex items-center gap-2 rounded-xl border border-line-subtle bg-panel px-2.5 py-2">
          <Avatar initial={comment.who} />
          <span className="min-w-0 flex-1 truncate text-sm">{comment.text}</span>
          <span className="hidden sm:block">{comment.chips}</span>
          <span className="shrink-0 rounded-md bg-raised px-2 py-1 text-xs text-fg">{comment.action}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- 8. scheduling, Reels and Stories

const WEEK = [
  { day: "Mon", date: "12" },
  { day: "Tue", date: "13", post: "Post" },
  { day: "Wed", date: "14" },
  { day: "Thu", date: "15", post: "Reel" },
  { day: "Fri", date: "16", post: "Story" },
  { day: "Sat", date: "17" },
  { day: "Sun", date: "18", post: "Post" },
];

export function ScheduleIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-3 p-4">
      <p className="flex items-center gap-1.5 text-xs font-medium text-fg-secondary">
        <CalendarDays className="size-3.5" /> This week
      </p>
      <div className="grid grid-cols-7 gap-1">
        {WEEK.map((item) => (
          <div key={item.day} className="flex flex-col items-center gap-1 rounded-lg border border-line-subtle bg-panel py-1.5">
            <span className="text-2xs text-fg-secondary">{item.day}</span>
            <span className="text-xs font-semibold">{item.date}</span>
            <span className={cn("h-1.5 w-4 rounded-full", item.post ? "bg-brand" : "bg-raised")} />
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-brand-line bg-panel p-2.5">
        <p className="flex flex-wrap items-center gap-1.5 text-xs">
          <Chip tone="brand">Reel</Chip>
          <span className="text-fg-secondary">Thu 15, 6:30 PM</span>
          <Chip>with @weave.studio</Chip>
        </p>
        <p className="mt-1.5 truncate text-sm">Linen season is here. Which colour would you pick?</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 9. catalogue, orders and payment links

const PRODUCTS = [
  { name: "Blue kurta", price: "₹1,499" },
  { name: "Linen shirt", price: "₹1,199" },
  { name: "Cotton dupatta", price: "₹649" },
];

export function OrdersIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-2.5 p-4">
      <div className="grid grid-cols-3 gap-1.5">
        {PRODUCTS.map((product) => (
          <div key={product.name} className="rounded-lg border border-line-subtle bg-panel p-1.5">
            <span className="block h-8 rounded-md bg-raised" />
            <span className="mt-1 block truncate text-xs">{product.name}</span>
            <span className="block text-xs font-semibold">{product.price}</span>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-line bg-panel p-2.5">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="font-medium">Order 1042 · Blue kurta, M</span>
          <Chip tone="success">
            <Check className="mr-0.5 inline size-3" />
            Paid
          </Chip>
        </div>
        <p className="mt-1 text-xs text-fg-secondary">Payment link sent in the chat. The money goes to your own account.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- 10. sequences

const STEPS = [
  { when: "Right away", what: "Thanks for your interest! Here is our size guide." },
  { when: "After 2 days", what: "Still thinking it over? Happy to help." },
  { when: "After 5 days", what: "Your size is still in stock." },
];

export function SequenceIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-2 p-4">
      <p className="flex items-center gap-1.5 text-xs font-medium text-fg-secondary">
        <UserRound className="size-3.5" /> A lead is captured
      </p>
      <ol className="space-y-1.5 border-l border-line pl-3">
        {STEPS.map((step) => (
          <li key={step.when} className="rounded-lg border border-line-subtle bg-panel px-2.5 py-1.5">
            <p className="text-2xs font-medium text-brand-fg">{step.when}</p>
            <p className="truncate text-xs">{step.what}</p>
          </li>
        ))}
      </ol>
      <p className="pl-1 text-xs text-fg-secondary">Stops as soon as they reply.</p>
    </div>
  );
}

// ---------------------------------------------------------------- 11. roles and assignment

const MEMBERS = [
  { name: "Priya", role: "Admin", open: 4 },
  { name: "Sam", role: "Agent", open: 7 },
  { name: "Kiran", role: "Agent", open: 3 },
];

export function TeamIllustration() {
  return (
    <div className="flex h-full flex-col justify-center gap-2 p-4">
      {MEMBERS.map((member) => (
        <div key={member.name} className="flex items-center gap-2.5 rounded-xl border border-line-subtle bg-panel px-2.5 py-1.5">
          <Avatar initial={member.name[0]} />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium">{member.name}</span>
            <span className="block text-xs text-fg-secondary">{member.open} open conversations</span>
          </span>
          <Chip tone={member.role === "Admin" ? "brand" : "neutral"}>{member.role}</Chip>
        </div>
      ))}
      <p className="flex items-center gap-1.5 pl-1 text-xs text-fg-secondary">
        <ShieldCheck className="size-3 shrink-0 text-brand-fg" /> Round-robin assignment, if you turn it on.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- the box

export const ILLUSTRATIONS = {
  draft: DraftIllustration,
  automation: AutomationIllustration,
  inbox: InboxIllustration,
  ask: AskIllustration,
  analytics: AnalyticsIllustration,
  comments: CommentsIllustration,
  schedule: ScheduleIllustration,
  orders: OrdersIllustration,
  sequence: SequenceIllustration,
  team: TeamIllustration,
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
