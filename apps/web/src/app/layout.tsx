import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";

import { ThemeSync } from "@/components/theme/ThemeSync";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { clerkAppearance } from "@/lib/clerk-appearance";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { colorValue } from "@/styles/tokens";
import "@/styles/globals.css";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Social Hood", template: "%s · Social Hood" },
  description: "One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.",
  // TR-FE-09: added to an iPhone's Home Screen, the app opens standalone (where push works).
  appleWebApp: { capable: true, title: "Social Hood", statusBarStyle: "black" },
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
        {/* Clerk Core 3: the provider sits inside <body>. */}
        <ClerkProvider
          appearance={clerkAppearance}
          // The sign-up card's subtitle (the Free plan needs no card, as the landing page says).
          localization={{ signUp: { start: { subtitle: "No credit card required." } } }}
          signInFallbackRedirectUrl="/app"
          signUpFallbackRedirectUrl="/app"
          afterSignOutUrl="/"
        >
          <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
          <Toaster />
          <ThemeSync />
        </ClerkProvider>
      </body>
    </html>
  );
}
