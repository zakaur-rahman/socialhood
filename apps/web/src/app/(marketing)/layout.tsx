import "@/components/site/site.css";

import type { Metadata, Viewport } from "next";

import { SiteFooter } from "@/components/marketing/SiteFooter";
import { SiteHeader } from "@/components/marketing/SiteHeader";
import { ThemePin } from "@/components/theme/ThemePin";
import { OG_IMAGE, SITE_DESCRIPTION, SITE_NAME, siteUrl } from "@/lib/marketing/site";
import { colorValue } from "@/styles/token-values";

// Relative canonical, Open Graph and Twitter URLs on the public pages resolve against the site URL.
// Pages that don't set their own openGraph (data-deletion's status, unsubscribe) inherit these.
export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  description: SITE_DESCRIPTION,
  openGraph: { type: "website", siteName: SITE_NAME, images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", images: [OG_IMAGE] },
};

// The browser bar on the site's paper (C-155); ThemeSync keeps it there after hydration.
export const viewport: Viewport = { themeColor: colorValue("paper") };

/**
 * The public site (C-155): header, the page, footer, in the owner's paper-and-night design. The
 * `.site` frame sets its own palette (styles/globals.css) and type (Geist, bold headings), so it
 * looks the same whatever theme the visitor chose for the app; <html> is pinned to the light scheme
 * (the root layout's head script on a first load, ThemePin on a client navigation). This replaces
 * the always-dark site of C-127 to C-129. Pages stay server-rendered and static; only the header's
 * account actions and phone menu, and the landing page's scenes, run in the browser.
 */
export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="site flex min-h-dvh flex-col">
      <ThemePin />
      <a href="#main" className="btn btn-main skip">
        Skip to content
      </a>
      {/* The bar sticks only over the page, not the footer (C-157): it scrolls away as the footer
          arrives, so it never sits over the footer's links on a phone (axe target-size). */}
      <div className="flex flex-1 flex-col">
        <SiteHeader />
        <div className="flex flex-1 flex-col">{children}</div>
      </div>
      <SiteFooter />
    </div>
  );
}
