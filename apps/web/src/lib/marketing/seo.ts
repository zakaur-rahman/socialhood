import type { Metadata } from "next";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { LEGAL, isSet } from "@/lib/legal";

import type { Pricing } from "./plans";
import { LOGO_PATH, OG_IMAGE, SITE_DESCRIPTION, SITE_NAME, SOCIAL_PROFILES, absoluteUrl, siteUrl } from "./site";

/** Search results cut titles and descriptions near these lengths (C-142); a test holds every public page to them. */
export const TITLE_MAX = 60;
export const DESCRIPTION_MAX = 160;

/** An article's dates, author and tags for Open Graph (og:type article). */
export type ArticleMeta = { publishedTime: string; modifiedTime: string; authors: string[]; tags: string[] };

/**
 * A public page's metadata: title, description, canonical URL, Open Graph and Twitter card with
 * the share image (/og.png). Named on every page because a page's openGraph replaces the
 * layout's whole openGraph. Relative URLs resolve against the marketing layout's metadataBase
 * (NEXT_PUBLIC_SITE_URL). A guide passes `article` (C-153); the English landing page and its
 * Hinglish version pass `languages`, the hreflang alternates, and the Hinglish page its `locale`.
 */
export function pageMetadata({
  title,
  description,
  path,
  absoluteTitle = false,
  article,
  languages,
  locale,
  feeds,
}: {
  title: string;
  description: string;
  path: string;
  /** The landing page names itself in full instead of "{title} · Amplychat". */
  absoluteTitle?: boolean;
  article?: ArticleMeta;
  /** hreflang alternates: language code to path, both directions (C-153). */
  languages?: Record<string, string>;
  /** Open Graph locale, e.g. "hi_IN"; the site default (en) when unset. */
  locale?: string;
  /** Feeds to advertise: title to path (`<link rel="alternate" type="application/rss+xml">`). */
  feeds?: Record<string, string>;
}): Metadata {
  const shareTitle = absoluteTitle ? title : `${title} · ${SITE_NAME}`;
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    alternates: {
      canonical: path,
      ...(languages ? { languages } : {}),
      ...(feeds ? { types: { "application/rss+xml": Object.entries(feeds).map(([feedTitle, url]) => ({ title: feedTitle, url })) } } : {}),
    },
    openGraph: {
      ...(article ? { type: "article" as const, ...article } : { type: "website" as const }),
      siteName: SITE_NAME,
      url: path,
      title: shareTitle,
      description,
      images: [OG_IMAGE],
      ...(locale ? { locale } : {}),
    },
    twitter: { card: "summary_large_image", title: shareTitle, description, images: [OG_IMAGE] },
  };
}

/**
 * hreflang for the landing page and its Hinglish version (C-153): each names both, and x-default is
 * the English page. "hi" rather than "hi-Latn": search engines document language and region codes
 * for hreflang, not scripts; the page's own lang attribute says hi-Latn.
 */
export const LANDING_LANGUAGES = { en: "/", hi: "/hi", "x-default": "/" } as const;

/** For pages that must never be indexed: sign-in and sign-up, the app, unsubscribe links, the 404. */
export const NO_INDEX: Metadata["robots"] = { index: false, follow: false };

type Env = Record<string, string | undefined>;

/**
 * Site ownership tags for Google Search Console, Bing Webmaster Tools and Meta's domain
 * verification, each from its env var and rendered only when set (C-142). Next writes
 * `google-site-verification`; the others go through `other`.
 */
export function verificationMetadata(env: Env = process.env): Metadata["verification"] | undefined {
  const google = env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION?.trim();
  const bing = env.NEXT_PUBLIC_BING_SITE_VERIFICATION?.trim();
  const facebook = env.NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION?.trim();
  const other: Record<string, string> = {};
  if (bing) other["msvalidate.01"] = bing;
  if (facebook) other["facebook-domain-verification"] = facebook;
  if (!google && !Object.keys(other).length) return undefined;
  return { ...(google ? { google } : {}), ...(Object.keys(other).length ? { other } : {}) };
}

// ---- structured data (schema.org JSON-LD)

/** Stable node ids, so the landing page's graph and the other pages can point at one Organization. */
export function organizationId(origin: string = siteUrl()): string {
  return `${origin}/#organization`;
}

function websiteId(origin: string): string {
  return `${origin}/#website`;
}

/**
 * The business: the product's name, the registered entity as legalName when the legal config has
 * it, the site, the logo and the support address. sameAs only once real profiles exist.
 */
export function organizationJsonLd(origin: string = siteUrl()): Record<string, unknown> {
  return {
    "@type": "Organization",
    "@id": organizationId(origin),
    name: SITE_NAME,
    ...(isSet(LEGAL.entityName) ? { legalName: LEGAL.entityName.trim() } : {}),
    url: `${origin}/`,
    logo: absoluteUrl(LOGO_PATH, origin),
    email: SUPPORT_EMAIL,
    contactPoint: { "@type": "ContactPoint", contactType: "customer support", email: SUPPORT_EMAIL },
    ...(SOCIAL_PROFILES.length ? { sameAs: [...SOCIAL_PROFILES] } : {}),
  };
}

/** The site itself. No SearchAction: the site has no search. */
export function webSiteJsonLd(origin: string = siteUrl()): Record<string, unknown> {
  return {
    "@type": "WebSite",
    "@id": websiteId(origin),
    name: SITE_NAME,
    url: `${origin}/`,
    description: SITE_DESCRIPTION,
    inLanguage: "en",
    publisher: { "@id": organizationId(origin) },
  };
}

/**
 * schema.org SoftwareApplication with only what is true: the name, what it does, that it runs in a
 * browser, and the offers the plan list priced (none when the API gave no prices, so a site
 * deployed without the API still has valid data). No ratings, reviews or download counts: there
 * are none.
 */
function softwareApplicationNode(pricing: Pricing, origin: string, publisher: Record<string, unknown>): Record<string, unknown> {
  const pro = pricing.plans.find((card) => card.plan === "pro" && card.available && card.offer);
  const offers = pro?.offer
    ? [
        { "@type": "Offer", name: "Free", price: "0", priceCurrency: pro.offer.currency, url: `${origin}/pricing` },
        { "@type": "Offer", name: "Pro", price: pro.offer.price, priceCurrency: pro.offer.currency, url: `${origin}/pricing` },
      ]
    : undefined;
  return {
    "@type": "SoftwareApplication",
    name: SITE_NAME,
    url: `${origin}/`,
    description: SITE_DESCRIPTION,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    inLanguage: "en",
    ...(offers ? { offers } : {}),
    publisher,
  };
}

/** The app on its own (the pricing page), with the Organization written out as its publisher. */
export function softwareApplicationJsonLd(pricing: Pricing, origin: string = siteUrl()): Record<string, unknown> {
  return { "@context": "https://schema.org", ...softwareApplicationNode(pricing, origin, organizationJsonLd(origin)) };
}

/** The FAQ section's questions and answers, as written on the page (plain text, no markup). */
export function faqPageJsonLd(
  faq: readonly { question: string; answer: string }[],
  origin: string = siteUrl(),
  id: string = `${origin}/#faq`,
): Record<string, unknown> {
  return {
    "@type": "FAQPage",
    "@id": id,
    mainEntity: faq.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
}

/** Home, then the page: every inner page sits one level below the landing page. */
export function breadcrumbJsonLd(name: string, path: string, origin: string = siteUrl()): Record<string, unknown> {
  return breadcrumbTrailJsonLd([{ name, path }], origin);
}

/** Home, then each level in order: a guide is Home, Guides, the guide (C-153). */
export function breadcrumbTrailJsonLd(trail: readonly { name: string; path: string }[], origin: string = siteUrl()): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: `${origin}/` },
      ...trail.map((level, index) => ({ "@type": "ListItem", position: index + 2, name: level.name, item: absoluteUrl(level.path, origin) })),
    ],
  };
}

/** What a guide's structured data needs (lib/marketing/guides). */
export type ArticleFields = {
  path: string;
  title: string;
  description: string;
  published: string;
  updated: string;
  author: string;
  tags: readonly string[];
  image?: string;
  faq?: readonly { question: string; answer: string }[];
};

/**
 * A guide (C-153): an Article written by the team (an Organization, as the byline says), published
 * by the business with its legal name, with its dates, and a FAQPage only when the guide has its
 * own questions and answers on the page. One @graph, so the FAQ sits beside the article.
 */
export function articleJsonLd(article: ArticleFields, origin: string = siteUrl()): Record<string, unknown> {
  const url = absoluteUrl(article.path, origin);
  const node = {
    "@type": "Article",
    "@id": `${url}#article`,
    headline: article.title,
    description: article.description,
    url,
    mainEntityOfPage: url,
    datePublished: article.published,
    dateModified: article.updated,
    inLanguage: "en",
    author: { "@type": "Organization", name: article.author, url: `${origin}/` },
    publisher: organizationJsonLd(origin),
    image: absoluteUrl(article.image ?? OG_IMAGE.url, origin),
    keywords: article.tags.join(", "),
  };
  return {
    "@context": "https://schema.org",
    "@graph": article.faq?.length ? [node, faqPageJsonLd(article.faq, origin, `${url}#faq`)] : [node],
  };
}

/** One @graph for the landing page: the Organization, the WebSite, the app and the FAQ. */
export function landingJsonLd(
  pricing: Pricing,
  faq: readonly { question: string; answer: string }[],
  origin: string = siteUrl(),
): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@graph": [
      organizationJsonLd(origin),
      webSiteJsonLd(origin),
      softwareApplicationNode(pricing, origin, { "@id": organizationId(origin) }),
      faqPageJsonLd(faq, origin),
    ],
  };
}

/** JSON for a <script type="application/ld+json">, with "<" escaped so it can't close the tag. */
export function jsonLdString(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
