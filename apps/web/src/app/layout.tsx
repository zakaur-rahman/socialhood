import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";

import { TooltipProvider } from "@/components/ui/tooltip";
import { clerkAppearance } from "@/lib/clerk-appearance";
import "@/styles/globals.css";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Social Hood", template: "%s · Social Hood" },
  description: "One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.",
  // TR-FE-09: added to an iPhone's Home Screen, the app opens standalone (where push works).
  appleWebApp: { capable: true, title: "Social Hood", statusBarStyle: "black" },
};

export const viewport: Viewport = { themeColor: "#000000" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable}`}>
      <body className="bg-canvas text-fg font-sans antialiased">
        {/* Clerk Core 3: the provider sits inside <body>. */}
        <ClerkProvider
          appearance={clerkAppearance}
          signInFallbackRedirectUrl="/app"
          signUpFallbackRedirectUrl="/app"
          afterSignOutUrl="/"
        >
          <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
          <Toaster theme="dark" position="bottom-right" />
        </ClerkProvider>
      </body>
    </html>
  );
}
