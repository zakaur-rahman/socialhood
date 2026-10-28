import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { SITE_NAME } from "@/lib/marketing/site";
import { cx } from "@/lib/cx";
import { cn } from "@/lib/utils";

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
    // No prefetch (C-152): the logo is on screen at once on every public page, and on the home page
    // its prefetch fetched the page being read (180 KB of RSC, then decoded on the main thread).
    <Link href="/" prefetch={false} className={cx("brand", className)}>
      <LogoMark className="size-7" />
      <span>{SITE_NAME}</span>
    </Link>
  );
}

export { MARKETING_CARD, MARKETING_CARD_GLASS, MARKETING_CARD_HOVER } from "./classes";

/** The site's button for each call to action (C-155, site.css): ink, outlined, or a quiet link. */
const CTA_CLASS = { primary: "btn btn-main", secondary: "btn btn-line", ghost: "btn btn-ghost" } as const;

export type CtaVariant = keyof typeof CTA_CLASS;

/** A call to action's classes: the site button in the matching variant, plus the caller's classes. */
export function ctaClass(variant: CtaVariant = "primary", className?: string): string {
  return cx(CTA_CLASS[variant], className);
}

/**
 * A link styled as a button. Links to Clerk's pages aren't prefetched: their scripts are heavy and
 * most visitors only read the page. Nor are links to a section of the page being read (`#…`):
 * prefetching them fetched that page again (C-152).
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
      prefetch={href.startsWith("#") ? false : prefetch}
      onClick={onClick}
      data-variant={variant}
      className={ctaClass(variant, className)}
    >
      {children}
    </Link>
  );
}

/** A section's kicker (C-155): a short sentence-case line in the accent above a heading. */
export const SECTION_EYEBROW = "kicker";

/** A page's h1 on the inner pages, and a section's h2 (site.css). */
export const PAGE_HEADING = "h-page";
export const SECTION_TITLE = "h2";
/** A band's heading inside a page (smaller than a landing section's). */
export const BAND_TITLE = "h-sec";

/**
 * A section's heading block on the site (C-155): the kicker, the heading and an optional lede,
 * left-aligned; `split` sets the lede beside the heading on wide screens, as the landing page does.
 */
export function SectionHeading({
  id,
  eyebrow,
  title,
  intro,
  className,
  level = 2,
  split = true,
}: {
  id: string;
  eyebrow: string;
  title: ReactNode;
  intro?: ReactNode;
  className?: string;
  /** 1 on a page whose first section this is (the pricing page has no other h1). */
  level?: 1 | 2;
  split?: boolean;
}) {
  const Heading = level === 1 ? "h1" : "h2";
  const head = (
    <div>
      <p className={SECTION_EYEBROW}>{eyebrow}</p>
      <Heading id={id} className={SECTION_TITLE}>
        {title}
      </Heading>
    </div>
  );
  if (!intro) return <div className={className}>{head}</div>;
  return split ? (
    <div className={cx("split-head", className)}>
      {head}
      <p className="lede">{intro}</p>
    </div>
  ) : (
    <div className={className}>
      {head}
      <p className="lede">{intro}</p>
    </div>
  );
}

/**
 * The page width every public section shares (site.css `.wrap`: 1240 px, 32 px gutters, 16 px on
 * phones). The caller's classes go on an inner box, so a narrow column (`max-w-3xl`) starts at the
 * same left edge as every other section instead of floating in the middle (C-155).
 */
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className="wrap">
      <div className={className}>{children}</div>
    </div>
  );
}
