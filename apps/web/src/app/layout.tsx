import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";

import { ThemeSync } from "@/components/theme/ThemeSync";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { clerkAppearance } from "@/lib/clerk-appearance";
import { verificationMetadata } from "@/lib/marketing/seo";
import { SITE_NAME, appOrigin, siteHref, siteUrl } from "@/lib/marketing/site";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { colorValue } from "@/styles/tokens";
import "@/styles/globals.css";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

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
};

// The browser bar: the dark canvas, the default. ThemeSync moves it for Light (and System on a light OS).
export const viewport: Viewport = { themeColor: colorValue("canvas") };

// C-146: with the app on its own host, sign-out lands on the public site's home page, which Clerk
// allows only for origins it is told about.
const app = appOrigin();
const allowedRedirectOrigins = app ? [siteUrl(), app] : undefined;

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
        {/* Clerk Core 3: the provider sits inside <body>. */}
        <ClerkProvider
          appearance={clerkAppearance}
          // The cards' titles name the product from SITE_NAME, not from the Clerk dashboard's
          // application name (C-139); the sign-up subtitle: the Free plan needs no card, as the
          // landing page says.
          localization={{
            signIn: { start: { title: `Sign in to ${SITE_NAME}`, subtitle: "Welcome back. Sign in to continue." } },
            signUp: { start: { title: `Create your ${SITE_NAME} account`, subtitle: "No credit card required." } },
          }}
          signInFallbackRedirectUrl="/app"
          signUpFallbackRedirectUrl="/app"
          afterSignOutUrl={siteHref("/")}
          allowedRedirectOrigins={allowedRedirectOrigins}
        >
          <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
          <Toaster />
          <ThemeSync />
        </ClerkProvider>
      </body>
    </html>
  );
}
