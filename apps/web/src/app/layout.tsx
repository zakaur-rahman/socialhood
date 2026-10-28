import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { RootAuth } from "@/components/auth/RootAuth";
import { ThemeSync } from "@/components/theme/ThemeSync";
import { verificationMetadata } from "@/lib/marketing/seo";
import { SITE_NAME, siteUrl } from "@/lib/marketing/site";
import { manifestLink } from "@/lib/pwa/manifest";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { colorValue } from "@/styles/tokens";
import "@/styles/globals.css";

// The app's type. Not preloaded since C-155: the public pages, which share this layout, set their
// own fonts (Funnel, components/site/fonts.ts) and never show Geist, so a preload there only took
// bandwidth from the first view. The app's stylesheet asks for it as soon as it renders text.
const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"], preload: false });
// Mono isn't preloaded (C-152): no page shows it above the fold (code samples, IDs, figures in the
// app), and a preload put its 25 KB ahead of the page on every first visit. It loads when used.
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"], preload: false });

export const metadata: Metadata = {
  // Absolute URLs (canonical, Open Graph) on every page resolve against the public origin (C-142).
  metadataBase: new URL(siteUrl()),
  applicationName: SITE_NAME,
  title: { default: SITE_NAME, template: `%s · ${SITE_NAME}` },
  description: "One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.",
  // Search Console, Bing Webmaster Tools and Meta domain verification: each tag only when its env var is set.
  verification: verificationMetadata(),
  // TR-FE-09: added to an iPhone's Home Screen, the app opens standalone (where push works).
  appleWebApp: { capable: true, title: SITE_NAME, statusBarStyle: "black" },
  // The install manifest: on every page with one origin, only the dashboard's otherwise (C-148).
  ...manifestLink().root,
};

// The browser bar: the dark canvas, the default. ThemeSync moves it for Light (and System on a light OS).
export const viewport: Viewport = { themeColor: colorValue("canvas") };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Dark is the default (C-129). The script below copies the user's choice from the `sh_theme`
    // cookie to `data-theme` before first paint, so the attribute can differ from what the server
    // rendered; hence suppressHydrationWarning. globals.css turns the attribute into color-scheme.
    <html lang="en" data-theme="dark" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="bg-canvas text-fg font-sans antialiased">
        {/* Clerk on every page with one origin; only in app/(clerk) when the app has its own host (C-148). */}
        {/* Toasts and tooltips belong to the app: app/(clerk)/layout.tsx mounts them (C-152). */}
        <RootAuth>
          {children}
          <ThemeSync />
        </RootAuth>
      </body>
    </html>
  );
}
