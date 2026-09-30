/**
 * The public site (marketing and legal pages): its origin for canonical URLs, Open Graph, the
 * sitemap and robots, and the links the header and footer share. Every claim the pages make comes
 * from the owner-approved product guide (knowledge/social-hood-product.md) and what is built.
 */

/** Used when NEXT_PUBLIC_SITE_URL is unset or not a URL: the production web app (WEB_BASE_URL). */
export const DEFAULT_SITE_URL = "https://app.socialhood.com";

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

export const SITE_NAME = "Social Hood";
export const SITE_TAGLINE = "AI inbox and automations for Instagram and WhatsApp";
export const SITE_DESCRIPTION =
  "Social Hood brings your Instagram DMs, comments and WhatsApp chats into one inbox, drafts or sends replies from your own business knowledge in English, Hindi and Hinglish, and runs comment and DM automations.";

/** The share image every public page names, drawn by app/(marketing)/og.png/route.tsx (next/og). */
export const OG_IMAGE = {
  url: "/og.png",
  width: 1200,
  height: 630,
  alt: "Social Hood: the AI inbox for businesses that sell on Instagram and WhatsApp",
  type: "image/png",
};

/** Clerk's pages (app/(auth)): sign-up lands on /app, which creates the first workspace (F-01). */
export const SIGN_UP_PATH = "/sign-up";
export const SIGN_IN_PATH = "/sign-in";
export const APP_PATH = "/app";

export const SECTION_IDS = {
  features: "features",
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
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
  { label: "Refund Policy", href: "/refunds" },
  { label: "Data deletion", href: "/data-deletion" },
] as const;

/** The public pages the sitemap lists. */
export const PUBLIC_PATHS = ["/", "/privacy", "/terms", "/refunds", "/data-deletion"] as const;
