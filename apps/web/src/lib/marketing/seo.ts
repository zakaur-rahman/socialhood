import type { Metadata } from "next";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { LEGAL, isSet } from "@/lib/legal";

import type { Pricing } from "./plans";
import { OG_IMAGE, SITE_DESCRIPTION, SITE_NAME, siteUrl } from "./site";

/**
 * A public page's metadata: title, description, canonical URL, Open Graph and Twitter card with
 * the share image (/og.png). Named on every page because a page's openGraph replaces the
 * layout's whole openGraph. Relative URLs resolve against the marketing layout's metadataBase
 * (NEXT_PUBLIC_SITE_URL).
 */
export function pageMetadata({
  title,
  description,
  path,
  absoluteTitle = false,
}: {
  title: string;
  description: string;
  path: string;
  /** The landing page names itself in full instead of "{title} · Social Hood". */
  absoluteTitle?: boolean;
}): Metadata {
  const shareTitle = absoluteTitle ? title : `${title} · ${SITE_NAME}`;
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    alternates: { canonical: path },
    openGraph: { type: "website", siteName: SITE_NAME, url: path, title: shareTitle, description, images: [OG_IMAGE] },
    twitter: { card: "summary_large_image", title: shareTitle, description, images: [OG_IMAGE] },
  };
}

/**
 * schema.org SoftwareApplication with only what is true: the name, what it does, that it runs in a
 * browser, and the offers the plan list priced (none when the API gave no prices). No ratings,
 * reviews or download counts: there are none.
 */
export function softwareApplicationJsonLd(pricing: Pricing, origin: string = siteUrl()): Record<string, unknown> {
  const pro = pricing.plans.find((card) => card.plan === "pro" && card.available && card.offer);
  const offers = pro?.offer
    ? [
        { "@type": "Offer", name: "Free", price: "0", priceCurrency: pro.offer.currency, url: `${origin}/#pricing` },
        { "@type": "Offer", name: "Pro", price: pro.offer.price, priceCurrency: pro.offer.currency, url: `${origin}/#pricing` },
      ]
    : undefined;
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: SITE_NAME,
    url: `${origin}/`,
    description: SITE_DESCRIPTION,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    inLanguage: "en",
    ...(offers ? { offers } : {}),
    ...(isSet(LEGAL.entityName)
      ? { provider: { "@type": "Organization", name: LEGAL.entityName.trim(), email: SUPPORT_EMAIL } }
      : {}),
  };
}

/** JSON for a <script type="application/ld+json">, with "<" escaped so it can't close the tag. */
export function jsonLdString(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
