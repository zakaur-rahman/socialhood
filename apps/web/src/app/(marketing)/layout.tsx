import type { Metadata } from "next";

import { SiteFooter } from "@/components/marketing/SiteFooter";
import { SiteHeader } from "@/components/marketing/SiteHeader";
import { OG_IMAGE, SITE_DESCRIPTION, SITE_NAME, siteUrl } from "@/lib/marketing/site";

// Relative canonical, Open Graph and Twitter URLs on the public pages resolve against the site URL.
// Pages that don't set their own openGraph (data-deletion's status, unsubscribe) inherit these.
export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  description: SITE_DESCRIPTION,
  openGraph: { type: "website", siteName: SITE_NAME, images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", images: [OG_IMAGE] },
};

/**
 * The public site: header, the page, footer. Pages stay server-rendered and static; only the
 * header's account actions and phone menu run in the browser. Each page renders its own <main>.
 */
export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:inline-flex focus:min-h-10 focus:items-center"
      >
        Skip to content
      </a>
      <SiteHeader />
      <div className="flex flex-1 flex-col">{children}</div>
      <SiteFooter />
    </div>
  );
}
