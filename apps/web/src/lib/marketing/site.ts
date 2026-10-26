/**
 * The public site (marketing and legal pages): its origin for canonical URLs, Open Graph, the
 * sitemap and robots, and the links the header and footer share. Every claim the pages make comes
 * from the owner-approved product guide (knowledge/social-hood-product.md) and what is built.
 */

/**
 * Used when NEXT_PUBLIC_SITE_URL is unset or not a URL: the canonical public origin (C-142). The
 * apex serves the site and the signed-in app (under /app) from one deployment; www redirects here.
 * The API's WEB_BASE_URL in production is the same origin.
 */
export const DEFAULT_SITE_URL = "https://amplychat.com";

/** The site's origin ("https://host[:port]", no trailing slash) from a URL, else the default. */
export function siteUrl(value: string | undefined = process.env.NEXT_PUBLIC_SITE_URL): string {
  if (value) {
    try {
      const url = new URL(value);
      if (url.protocol === "https:" || url.protocol === "http:") return url.origin;
    } catch {
      // not a URL: fall through to the default
    }
  }
  return DEFAULT_SITE_URL;
}

/** An absolute URL on the site for a path ("/privacy"). */
export function absoluteUrl(path: string, origin: string = siteUrl()): string {
  return new URL(path, `${origin}/`).href;
}

export const SITE_NAME = "Amplychat";
export const SITE_TAGLINE = "AI inbox and automations for Instagram and WhatsApp";
/** The landing page's title after the name: "Amplychat · …" stays within 60 characters. */
export const SITE_TITLE_LINE = "AI inbox for Instagram and WhatsApp";
/** The landing page's description (and the default): at most 160 characters, for search results. */
export const SITE_DESCRIPTION =
  "Instagram DMs, comments and WhatsApp in one inbox. AI replies from your business knowledge in English, Hindi and Hinglish, plus comment and DM automations.";

/** The logo for structured data (Organization.logo): the 512 px app icon, a square PNG. */
export const LOGO_PATH = "/icons/icon-512.png";

/**
 * The business's own social profiles, for Organization.sameAs. Empty until real ones exist: a
 * profile is listed here only once it is live and run by the business.
 */
export const SOCIAL_PROFILES: readonly string[] = [];

/** The share image every public page names, drawn by app/(marketing)/og.png/route.tsx (next/og). */
export const OG_IMAGE = {
  url: "/og.png",
  width: 1200,
  height: 630,
  alt: "Amplychat: the AI inbox for businesses that sell on Instagram and WhatsApp",
  type: "image/png",
};

/** Clerk's pages (app/(auth)): sign-up lands on /app, which creates the first workspace (F-01). */
export const SIGN_UP_PATH = "/sign-up";
export const SIGN_IN_PATH = "/sign-in";
export const APP_PATH = "/app";

export const SECTION_IDS = {
  features: "features",
  integrations: "integrations",
  howItWorks: "how-it-works",
  pricing: "pricing",
  faq: "faq",
} as const;

/** The header's links; they point at the landing page's sections from every page. */
export const NAV_LINKS = [
  { label: "Features", href: `/#${SECTION_IDS.features}` },
  { label: "How it works", href: `/#${SECTION_IDS.howItWorks}` },
  { label: "Pricing", href: `/#${SECTION_IDS.pricing}` },
  { label: "FAQ", href: `/#${SECTION_IDS.faq}` },
] as const;

export const LEGAL_LINKS = [
  { label: "Privacy policy", href: "/privacy" },
  { label: "Terms of service", href: "/terms" },
  { label: "Refund and cancellation", href: "/refunds" },
  { label: "Shipping and delivery", href: "/shipping" },
  { label: "Data deletion", href: "/data-deletion" },
  { label: "Contact us", href: "/contact" },
] as const;

/** The public pages the sitemap lists. */
export const PUBLIC_PATHS = [
  "/",
  "/pricing",
  "/switch-from-manychat",
  "/compare/manychat",
  "/compare/interakt",
  "/features/comment-intelligence",
  "/features/ai-inbox",
  "/features/publishing",
  "/privacy",
  "/terms",
  "/refunds",
  "/shipping",
  "/data-deletion",
  "/contact",
  "/developers/api",
  "/security",
] as const;

/**
 * What robots.txt keeps crawlers out of: the signed-in app, sign-in and sign-up, the digest's
 * unsubscribe links, the dev-only pages and route handlers under /api. "/app$" and "/app/" rather
 * than "/app", which would also match /apple-icon.png. Those pages carry noindex too (C-142).
 */
export const ROBOTS_DISALLOW = ["/app$", "/app/", "/w/", "/sign-in", "/sign-up", "/unsubscribe", "/dev/", "/api/"] as const;

/**
 * When each marketing page's content last changed in a way a reader would notice (an ISO date).
 * Bump the date when you change a page's copy. The legal pages use their "Last updated" date
 * (LEGAL_DOCUMENTS), so they are not listed here.
 * A build date would tell crawlers every page changed on every deploy, which isn't true.
 */
export const PAGE_UPDATED: Partial<Record<(typeof PUBLIC_PATHS)[number], string>> = {
  "/": "2026-10-26",
  "/pricing": "2026-10-26",
  "/switch-from-manychat": "2026-10-26",
  "/compare/manychat": "2026-10-26",
  "/compare/interakt": "2026-10-26",
  "/features/comment-intelligence": "2026-10-26",
  "/features/ai-inbox": "2026-10-26",
  "/features/publishing": "2026-10-26",
  "/data-deletion": "2026-10-26",
  "/contact": "2026-10-26",
  "/developers/api": "2026-10-26",
  "/security": "2026-10-26",
};

/** The footer's "Compare and learn" links to the go-to-market pages (GR-37). */
export const LEARN_LINKS = [
  { label: "Plans and limits", href: "/pricing" },
  { label: "Switch from Manychat", href: "/switch-from-manychat" },
  { label: "Amplychat vs Manychat", href: "/compare/manychat" },
  { label: "Amplychat vs Interakt", href: "/compare/interakt" },
  { label: "Comment intelligence", href: "/features/comment-intelligence" },
  { label: "The AI inbox", href: "/features/ai-inbox" },
  { label: "Publishing", href: "/features/publishing" },
  { label: "Public API", href: "/developers/api" },
] as const;
