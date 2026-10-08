import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { EYEBROW, MARKETING_HEADING } from "@/styles/tokens";

/**
 * The logo mark: the shell-gradient tile with the chat bubble (UX-SH-01, public/icons). The SVG has
 * no colours of its own (UI-ISS-095): the bubble is `currentColor`, `on-brand` from the tile, and the
 * dots are `brand-deep`.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      data-logo-mark=""
      className={cn("bg-shell-gradient grid size-8 shrink-0 place-items-center rounded-lg text-on-brand", className)}
    >
      <svg viewBox="0 0 24 24" className="size-[62%]" fill="none">
        <path d="M5 5.5h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-8l-4.5 3.5V16.5H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z" fill="currentColor" />
        <g className="fill-brand-deep">
          <circle cx="8" cy="11" r="1.25" />
          <circle cx="12" cy="11" r="1.25" />
          <circle cx="16" cy="11" r="1.25" />
        </g>
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

/** The Button variant behind each call to action. */
const CTA_BUTTON = { primary: "default", secondary: "secondary", ghost: "ghost" } as const;

export type CtaVariant = keyof typeof CTA_BUTTON;

/**
 * C-068's extras on top of the Button recipe: a small lift on hover (motion-safe only; the
 * transition adds `translate` to the recipe's colour properties), the primary's brand glow
 * (DESIGN_SYSTEM §6: `shadow-brand/10–25`, marketing only), and the ghost's secondary text, like
 * the nav links beside it.
 */
const CTA_EXTRA: Record<CtaVariant, string> = {
  primary: "shadow-lg shadow-brand/25",
  secondary: "",
  ghost: "text-fg-secondary",
};
const LIFT = "transition-[color,background-color,border-color,filter,translate] motion-safe:hover:-translate-y-0.5";

/**
 * A call to action's classes: Button's `xl` (40 px on every pointer, so 40 px on touch too) in the
 * matching variant, merged with the marketing extras and the caller's classes (padding, width).
 */
export function ctaClass(variant: CtaVariant = "primary", className?: string): string {
  return cn(buttonVariants({ variant: CTA_BUTTON[variant], size: "xl" }), LIFT, CTA_EXTRA[variant], className);
}

/**
 * A link styled as a button, with Button's data attributes. Links to Clerk's pages aren't
 * prefetched: their scripts are heavy and most visitors only read the page.
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
  variant?: CtaVariant;
  className?: string;
  children: ReactNode;
  prefetch?: boolean;
  /** Only from client components (the phone menu closes itself). */
  onClick?: () => void;
}) {
  return (
    <Link
      href={href as Route}
      prefetch={prefetch}
      onClick={onClick}
      data-slot="button"
      data-variant={CTA_BUTTON[variant]}
      data-size="xl"
      className={ctaClass(variant, className)}
    >
      {children}
    </Link>
  );
}

/** A section's eyebrow: the EYEBROW role in the brand's text colour. */
export const SECTION_EYEBROW = cn(EYEBROW, "text-brand-fg");

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
      <p className={SECTION_EYEBROW}>{eyebrow}</p>
      <h2 id={id} className={cn(MARKETING_HEADING, "mt-3 text-balance")}>
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
