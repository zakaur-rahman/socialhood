import type { Metadata } from "next";

import { SiteFooter } from "@/components/marketing/SiteFooter";
import { SiteHeader } from "@/components/marketing/SiteHeader";
import { SiteNotFoundActions } from "@/components/not-found/NotFoundActions";
import { NotFoundPage } from "@/components/not-found/NotFoundPage";
import { ThemePin } from "@/components/theme/ThemePin";

// A 404 is never worth indexing; Next answers with status 404 for an unknown URL.
export const metadata: Metadata = { title: "Page not found", robots: { index: false, follow: true } };

/**
 * An address that matches no route (and a `notFound()` outside the workspace): the public site's
 * frame, always dark like the marketing pages, with the 404 page between the header and footer.
 * A signed-in visitor sees "Open the app" in place of "Sign in". A missing page inside a
 * workspace is `w/[slug]/not-found.tsx`, which keeps the app shell instead.
 */
export default function RootNotFound() {
  return (
    <div className="scheme-dark flex min-h-dvh flex-col bg-canvas bg-ambient bg-fixed">
      <ThemePin />
      <SiteHeader />
      <main id="main" className="flex flex-1 flex-col">
        <NotFoundPage>
          <SiteNotFoundActions />
        </NotFoundPage>
      </main>
      <SiteFooter />
    </div>
  );
}
