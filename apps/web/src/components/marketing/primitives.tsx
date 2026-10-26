import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button";
import { SITE_NAME } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";
import { EYEBROW, MARKETING_HEADING } from "@/styles/tokens";

/**
 * The logo mark (C-140): the shell-gradient tile with the "amp bubble", a chat bubble holding three
 * rising bars (UX-SH-01, public/icons, scripts/generate-icons.mjs draws the same shape). The SVG has
 * no colours of its own (UI-ISS-095): the bubble is `currentColor`, `on-brand` from the tile, and the
 * bars are `brand-deep`.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      data-logo-mark=""
      className={cn("bg-shell-gradient grid size-8 shrink-0 place-items-center rounded-lg text-on-brand", className)}
    >
      <svg viewBox="0 0 64 64" className="size-full" fill="none">
        <path d={LOGO_BUBBLE_PATH} fill="currentColor" />
        <g className="fill-brand-deep">
          {LOGO_BARS.map(([x, y, height]) => (
            <rect key={x} x={x} y={y} width="5" height={height} rx="2.5" />
          ))}
        </g>
      </svg>
    </span>
  );
}

/** The mark's bubble on a 64-unit tile, shared with the share image (og.tsx). */
export const LOGO_BUBBLE_PATH = "M20 13H44Q52 13 52 21V35Q52 43 44 43H29L19 51V43Q12 43 12 35V21Q12 13 20 13Z";

/** The mark's three rising bars as [x, y, height], 5 units wide, on the same 64-unit tile. */
export const LOGO_BARS = [
  [21.5, 30, 7],
  [29.5, 25, 12],
  [37.5, 19, 18],
] as const;

/** The logo linking home; the wordmark is the link's name. */
export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("flex min-h-10 items-center gap-2.5 rounded-lg", className)}>
      <LogoMark />
      <span className="text-base font-semibold tracking-tight">{SITE_NAME}</span>
    </Link>
  );
}

/**
 * The marketing card surface (C-127): `rounded-2xl` (DESIGN_SYSTEM §4), a `line` edge and the
 * `panel` fill. A card that reacts to hover adds `MARKETING_CARD_HOVER`; a card laid over the page
 * glow wears the `panel-glass` fill instead. Add padding and layout at the call site.
 */
export const MARKETING_CARD = "rounded-2xl border border-line bg-panel";
export const MARKETING_CARD_GLASS = "rounded-2xl border border-line bg-panel-glass";
export const MARKETING_CARD_HOVER = "transition-colors duration-slow hover:border-line-strong";

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
  primary: "shadow-glow-button",
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
  level = 2,
}: {
  id: string;
  eyebrow: string;
  title: string;
  intro?: ReactNode;
  className?: string;
  /** 1 on a page whose first section this is (the pricing page has no other h1). */
  level?: 1 | 2;
}) {
  const Heading = level === 1 ? "h1" : "h2";
  return (
    <div className={cn("mx-auto max-w-2xl text-center", className)}>
      <p className={SECTION_EYEBROW}>{eyebrow}</p>
      <Heading id={id} className={cn(MARKETING_HEADING, "mt-3 text-balance")}>
        {title}
      </Heading>
      {intro ? <p className="mt-4 text-base leading-relaxed text-pretty text-fg-secondary">{intro}</p> : null}
    </div>
  );
}

/** The page width every marketing section shares, with a 16 px gutter on phones. */
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-6xl px-4 sm:px-6", className)}>{children}</div>;
}
