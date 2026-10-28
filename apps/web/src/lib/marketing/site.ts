/**
 * The public site (marketing and legal pages): its origin for canonical URLs, Open Graph, the
 * sitemap and robots, and the links the header and footer share. Every claim the pages make comes
 * from the owner-approved product guide (knowledge/social-hood-product.md) and what is built.
 */

/**
 * Used when NEXT_PUBLIC_SITE_URL is unset or not a URL: the canonical public origin (C-142); www
 * redirects here. In production the signed-in app is on its own host, NEXT_PUBLIC_APP_URL
 * (https://dashboard.amplychat.com, C-146), served by the same deployment.
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

/**
 * The signed-in app's own origin (C-146), from NEXT_PUBLIC_APP_URL: "https://dashboard.amplychat.com"
 * in production. Null when unset, not an http(s) URL, or the same origin as the site: then the app
 * and the site share one origin (local dev, e2e, CI) and every link stays relative.
 */
export function appOrigin(
  value: string | undefined = process.env.NEXT_PUBLIC_APP_URL,
  site: string = siteUrl(),
): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    return url.origin === site ? null : url.origin;
  } catch {
    return null;
  }
}

/**
 * A link into the app ("/sign-up", "/app?plan=pro"): absolute on the app's origin when it has its
 * own (C-146), so a marketing CTA needs no redirect hop; the path as it is otherwise.
 */
export function appUrl(path: string, origin: string | null = appOrigin()): string {
  return origin ? absoluteUrl(path, origin) : path;
}

/**
 * A link from the app to a public page ("/privacy", "/pricing"): absolute on the site when the app
 * has its own origin (C-146); the path as it is otherwise.
 */
export function siteHref(path: string, origin: string | null = appOrigin()): string {
  return origin ? absoluteUrl(path, siteUrl()) : path;
}

export const SITE_NAME = "Amplychat";
export const SITE_TAGLINE = "AI inbox and automations for Instagram and WhatsApp";
/** The landing page's title after the name: "Amplychat · …" stays within 60 characters. */
export const SITE_TITLE_LINE = "AI inbox for Instagram and WhatsApp";
/** The landing page's description (and the default): at most 160 characters, for search results. */
export const SITE_DESCRIPTION =
  "Instagram DMs, comments and WhatsApp in one inbox for businesses and creators. AI replies from your own knowledge, plus comment and DM automations.";

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
  alt: "Amplychat: the AI inbox for businesses and creators on Instagram and WhatsApp",
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
  { label: "Guides", href: "/guides" },
] as const;

export const LEGAL_LINKS = [
  { label: "Privacy policy", href: "/privacy" },
  { label: "Terms of service", href: "/terms" },
  { label: "Refund and cancellation", href: "/refunds" },
  { label: "Shipping and delivery", href: "/shipping" },
  { label: "Data deletion", href: "/data-deletion" },
  { label: "Contact us", href: "/contact" },
  // The security track's responsible-disclosure page (C-143); it exists once the branches combine.
  { label: "Security", href: "/security" },
] as const;

/**
 * The public pages the sitemap lists. Each guide (/guides/{slug}, lib/marketing/guides) is added by
 * the sitemap itself, and /guides takes its date from the newest guide (C-153).
 */
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
  "/guides",
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
  "/": "2026-10-29",
  "/pricing": "2026-10-29",
  "/switch-from-manychat": "2026-10-29",
  "/compare/manychat": "2026-10-29",
  "/compare/interakt": "2026-10-29",
  "/features/comment-intelligence": "2026-10-26",
  "/features/ai-inbox": "2026-10-29",
  "/features/publishing": "2026-10-26",
  "/data-deletion": "2026-10-26",
  "/contact": "2026-10-26",
  "/developers/api": "2026-10-26",
  "/security": "2026-10-26",
};

/**
 * The footer's "Compare and learn" links to the go-to-market pages (GR-37); `lang` marks a label
 * that isn't English. The guides are in NAV_LINKS (header and footer). The Hinglish page (C-153)
 * was taken down in C-155: /hi redirects to /.
 */
export const LEARN_LINKS: readonly { label: string; href: string; lang?: string }[] = [
  { label: "Plans and limits", href: "/pricing" },
  { label: "Switch from Manychat", href: "/switch-from-manychat" },
  { label: "Amplychat vs Manychat", href: "/compare/manychat" },
  { label: "Amplychat vs Interakt", href: "/compare/interakt" },
  { label: "Comment intelligence", href: "/features/comment-intelligence" },
  { label: "The AI inbox", href: "/features/ai-inbox" },
  { label: "Publishing", href: "/features/publishing" },
  { label: "Public API", href: "/developers/api" },
];
