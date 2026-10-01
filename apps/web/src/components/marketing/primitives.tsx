import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The logo mark: the shell-gradient tile with the chat bubble (UX-SH-01, public/icons). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span aria-hidden className={cn("bg-shell-gradient grid size-8 shrink-0 place-items-center rounded-[10px]", className)}>
      <svg viewBox="0 0 24 24" className="size-[62%]" fill="none">
        <path d="M5 5.5h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-8l-4.5 3.5V16.5H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z" fill="#fff" />
        <circle cx="8" cy="11" r="1.25" fill="#20338A" />
        <circle cx="12" cy="11" r="1.25" fill="#20338A" />
        <circle cx="16" cy="11" r="1.25" fill="#20338A" />
      </svg>
    </span>
  );
}

/** The logo linking home; the wordmark is the link's name. */
export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("flex min-h-10 items-center gap-2.5 rounded-lg", className)}>
      <LogoMark />
      <span className="text-base font-semibold tracking-tight">Social Hood</span>
    </Link>
  );
}

// Focus rings come from globals.css (:focus-visible, the brand outline).
// C-068: a small lift on hover, only without reduced motion.
const CTA_BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium whitespace-nowrap transition-[filter,background-color,color,translate,box-shadow] duration-150 motion-safe:hover:-translate-y-0.5";

export const CTA_CLASS = {
  primary: cn(CTA_BASE, "bg-brand-gradient text-white shadow-lg shadow-brand/25 hover:shadow-brand/40 hover:brightness-110"),
  secondary: cn(CTA_BASE, "border border-line-strong bg-raised text-fg hover:bg-raised-hover"),
  ghost: cn(CTA_BASE, "text-fg-secondary hover:bg-raised hover:text-fg"),
} as const;

/**
 * A link styled as a button. Links to Clerk's pages aren't prefetched: their scripts are heavy and
 * most visitors only read the page.
 */
export function CtaLink({
  href,
  variant = "primary",
  className,
  children,
  prefetch,
  onClick,
}: {
  href: string;
  variant?: keyof typeof CTA_CLASS;
  className?: string;
  children: ReactNode;
  prefetch?: boolean;
  /** Only from client components (the phone menu closes itself). */
  onClick?: () => void;
}) {
  return (
    <Link href={href as Route} prefetch={prefetch} onClick={onClick} className={cn(CTA_CLASS[variant], className)}>
      {children}
    </Link>
  );
}

/** A landing section's heading block: a small eyebrow, the h2 and an optional intro. */
export function SectionHeading({
  id,
  eyebrow,
  title,
  intro,
  className,
}: {
  id: string;
  eyebrow: string;
  title: string;
  intro?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto max-w-2xl text-center", className)}>
      <p className="text-xs font-semibold tracking-[0.14em] text-brand-fg uppercase">{eyebrow}</p>
      <h2 id={id} className="mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      {intro ? <p className="mt-4 text-base leading-relaxed text-pretty text-fg-secondary">{intro}</p> : null}
    </div>
  );
}

/** The page width every marketing section shares, with a 16 px gutter on phones. */
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-6xl px-4 sm:px-6", className)}>{children}</div>;
}
