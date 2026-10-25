import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { NotFoundIllustration } from "./NotFoundIllustration";
import { RequestedPath } from "./RequestedPath";

/**
 * The 404 page's body, for the public site and the signed-in app: the illustration, a plain
 * heading, the path that was asked for (small, so a mistyped link is easy to spot) and the ways
 * out, passed in as `children`. The caller supplies the frame (site header and footer, or the app
 * shell, which has the <main> landmark), so this is only the middle.
 */
export function NotFoundPage({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      data-testid="not-found-page"
      className={cn("flex flex-1 flex-col items-center justify-center gap-4 px-4 py-12 text-center sm:py-16", className)}
    >
      <NotFoundIllustration className="w-full max-w-xs sm:max-w-sm" />
      <p className="text-sm font-medium text-brand-fg">Error 404</p>
      <h1 className="text-balance text-2xl font-semibold sm:text-3xl">We can&apos;t find that page</h1>
      <p className="max-w-md text-balance text-fg-secondary">
        The link may be mistyped, or the page may have moved or been deleted. These will get you going again.
      </p>
      <RequestedPath />
      <div className="mt-2 flex flex-wrap items-center justify-center gap-2">{children}</div>
    </div>
  );
}
