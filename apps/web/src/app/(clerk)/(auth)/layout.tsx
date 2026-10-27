import type { Metadata } from "next";

import { NO_INDEX } from "@/lib/marketing/seo";

// Sign-in and sign-up are never search results (C-142); robots.txt keeps crawlers out too.
export const metadata: Metadata = { robots: NO_INDEX };

/** The sign-in and sign-up pages render their own <main> (AuthShell); this adds the skip link. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-brand-strong text-sm font-medium text-on-brand focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:inline-flex focus:min-h-10 focus:items-center focus:px-4"
      >
        Skip to content
      </a>
      {children}
    </>
  );
}
