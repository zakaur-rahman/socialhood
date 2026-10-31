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
export const SITE_TAGLINE = "AI inbox and automations for Instagram, WhatsApp and website chat";
/** The landing page's title after the name: "Amplychat · …" stays within 60 characters. */
export const SITE_TITLE_LINE = "AI inbox for Instagram, WhatsApp and web chat";
/** The landing page's description (and the default): at most 160 characters, for search results. */
export const SITE_DESCRIPTION =
  "One AI inbox for Instagram DMs and comments, WhatsApp and your website chat. Replies from your own knowledge, plus comment-to-DM automations.";

/** The logo for structured data (Organization.logo): the 512 px app icon, a square PNG. */
export const LOGO_PATH = "/icons/icon-512.png";
/** Its width and height in pixels. */
export const LOGO_SIZE = 512;

/**
 * The business's own social profiles: Organization.sameAs and the footer's links. A profile is
 * listed here only once it is live and run by the business (Instagram and the Facebook Page, owner
 * 2026-10-31). LinkedIn (linkedin.com/company/amplychat) is held back for now at the owner's request;
 * the network and its glyph stay supported, so adding it back is one line here.
 */
export const SOCIAL_PROFILES: readonly { network: "instagram" | "facebook" | "linkedin"; label: string; url: string }[] = [
  { network: "instagram", label: "Instagram", url: "https://www.instagram.com/amplychat_67/" },
  { network: "facebook", label: "Facebook", url: "https://www.facebook.com/profile.php?id=61595928331470" },
];

/** The share image every public page names, drawn by app/(marketing)/og.png/route.tsx (next/og). */
export const OG_IMAGE = {
  url: "/og.png",
  width: 1200,
  height: 630,
  alt: "Amplychat: Every DM. Every comment. One inbox. For Instagram, WhatsApp and website chat.",
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

/** The two explainer pages (C-160): the header, the footer and the 404 link here. */
export const FEATURES_PATH = "/features";
export const HOW_IT_WORKS_PATH = "/how-it-works";

/**
 * The header's links (bar and phone menu). Features and How it works have their own pages (C-160);
 * Pricing and FAQ lead to /pricing and /faq (C-163, the SEO audit's link-equity finding), not the
 * landing's sections, whose anchors stay for in-page links.
 */
export const NAV_LINKS = [
  { label: "Features", href: FEATURES_PATH },
  { label: "How it works", href: HOW_IT_WORKS_PATH },
  { label: "Pricing", href: "/pricing" },
  { label: "FAQ", href: "/faq" },
  { label: "Guides", href: "/guides" },
] as const;

export const LEGAL_LINKS = [
  { label: "Privacy policy", href: "/privacy" },
  { label: "Terms of service", href: "/terms" },
  { label: "Security", href: "/security" },
  { label: "Data deletion", href: "/data-deletion" },
  { label: "Refund and cancellation", href: "/refunds" },
  { label: "Shipping and delivery", href: "/shipping" },
  // C-156: the legal agent's pages; they exist once the C-156 branches combine.
  { label: "Subprocessors", href: "/subprocessors" },
  { label: "Cookies", href: "/cookies" },
  { label: "Data processing agreement", href: "/dpa" },
  { label: "Accessibility", href: "/accessibility" },
  { label: "Contact us", href: "/contact" },
] as const;


/**
 * The hosted status page (C-156), from NEXT_PUBLIC_STATUS_URL: an http(s) URL, or null when it is
 * unset or not a URL, and then the footer has no Status link. Read at build time like every
 * NEXT_PUBLIC_* value.
 */
export function statusUrl(value: string | undefined = process.env.NEXT_PUBLIC_STATUS_URL): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

export type FooterLink = { label: string; href: string; external?: boolean };
export type FooterColumn = { id: string; title: string; links: FooterLink[] };

/**
 * The footer's columns (C-156). Status shows only when the status page is configured. The social
 * profiles (SOCIAL_PROFILES) sit under the brand, not in a column. The /shipping page is labelled
 * "Delivery" here (C-161 v2): the business ships nothing physical; the page keeps its URL and its
 * "Shipping and Delivery Policy" title, which payment-provider reviews look for.
 */
export function footerColumns(status: string | null = statusUrl()): FooterColumn[] {
  return [
    {
      id: "product",
      title: "Product",
      links: [
        { label: "Features", href: FEATURES_PATH },
        { label: "Pricing", href: "/pricing" },
        { label: "How it works", href: HOW_IT_WORKS_PATH },
        { label: "Automations", href: "/automations" },
        { label: "What's new", href: "/changelog" },
        ...(status ? [{ label: "Status", href: status, external: true }] : []),
        { label: "Sign in", href: appUrl(SIGN_IN_PATH) },
      ],
    },
    {
      id: "solutions",
      title: "Solutions",
      links: [
        { label: "For creators", href: "/for-creators" },
        { label: "For businesses", href: "/for-businesses" },
        { label: "Developers", href: "/developers/api" },
        { label: "MCP", href: "/mcp" },
        { label: "Connect AI apps", href: "/developers/mcp" },
      ],
    },
    {
      id: "compare",
      title: "Compare",
      links: [
        { label: "vs Manychat", href: "/compare/manychat" },
        { label: "vs Interakt", href: "/compare/interakt" },
        { label: "Switch from Manychat", href: "/switch-from-manychat" },
        // C-163 (gloss)
        { label: "Manychat alternatives", href: "/compare/manychat-alternatives" },
        { label: "All comparisons", href: "/compare" },
      ],
    },
    {
      id: "resources",
      title: "Resources",
      links: [
        { label: "Guides", href: "/guides" },
        // C-163 (gloss)
        { label: "Glossary", href: "/glossary" },
        { label: "Common questions", href: "/faq" },
        { label: "AI info", href: "/ai-info" },
        { label: "Safety", href: "/safety" },
        { label: "Contact", href: "/contact" },
      ],
    },
    {
      id: "legal",
      title: "Legal and trust",
      links: [
        { label: "Privacy", href: "/privacy" },
        { label: "Terms", href: "/terms" },
        { label: "Security", href: "/security" },
        { label: "Data deletion", href: "/data-deletion" },
        { label: "Refunds", href: "/refunds" },
        { label: "Delivery", href: "/shipping" },
        { label: "Subprocessors", href: "/subprocessors" },
        { label: "Cookies", href: "/cookies" },
        { label: "DPA", href: "/dpa" },
        { label: "Accessibility", href: "/accessibility" },
      ],
    },
  ];
}

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
  "/compare",
  "/compare/linkdm",
  "/compare/instantdm",
  "/compare/inro",
  "/compare/creatorflow",
  "/compare/wati",
  "/compare/aisensy",
  "/compare/spur",
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
  "/developers/mcp",
  "/developers/mcp/api-key",
  "/mcp",
  "/security",
  "/guides",
  // C-156 (pages)
  "/for-creators",
  "/for-businesses",
  "/safety",
  "/changelog",
  "/ai-info",
  "/subprocessors",
  "/cookies",
  "/dpa",
  "/accessibility",
  // C-157: every question, out of the landing page
  "/faq",
  // C-160: the explainer pages
  "/how-it-works",
  "/features",
  // C-163 (auto): the automation and channel pages and their hub
  "/automations",
  "/instagram/comment-to-dm",
  "/instagram/story-replies",
  "/instagram/dm-keywords",
  "/instagram/conversation-starters",
  "/whatsapp/auto-reply",
  "/website-chat",
  // C-163 (gloss): each term (/glossary/{slug}) is added by the sitemap itself
  "/glossary",
  "/compare/manychat-alternatives",
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
  "/": "2026-10-30",
  "/pricing": "2026-10-29",
  "/switch-from-manychat": "2026-10-29",
  "/compare/manychat": "2026-10-29",
  "/compare/interakt": "2026-10-29",
  "/compare": "2026-10-29",
  "/compare/linkdm": "2026-10-29",
  "/compare/instantdm": "2026-10-29",
  "/compare/inro": "2026-10-29",
  "/compare/creatorflow": "2026-10-29",
  "/compare/wati": "2026-10-29",
  "/compare/aisensy": "2026-10-29",
  "/compare/spur": "2026-10-29",
  "/features/comment-intelligence": "2026-10-31",
  "/features/ai-inbox": "2026-10-31",
  "/features/publishing": "2026-10-31",
  "/data-deletion": "2026-10-26",
  "/contact": "2026-10-26",
  "/developers/api": "2026-10-26",
  "/developers/mcp": "2026-11-01",
  "/developers/mcp/api-key": "2026-11-01",
  "/mcp": "2026-11-01",
  "/security": "2026-10-26",
  "/for-creators": "2026-10-29",
  "/for-businesses": "2026-10-29",
  "/safety": "2026-10-29",
  "/ai-info": "2026-10-29",
  "/faq": "2026-10-30",
  "/how-it-works": "2026-10-31",
  "/features": "2026-10-31",
  // C-163 (auto)
  "/automations": "2026-10-31",
  "/instagram/comment-to-dm": "2026-10-31",
  "/instagram/story-replies": "2026-10-31",
  "/instagram/dm-keywords": "2026-10-31",
  "/instagram/conversation-starters": "2026-10-31",
  "/whatsapp/auto-reply": "2026-10-31",
  "/website-chat": "2026-10-31",
  // C-163 (gloss)
  "/glossary": "2026-10-31",
  "/compare/manychat-alternatives": "2026-10-31",
};
