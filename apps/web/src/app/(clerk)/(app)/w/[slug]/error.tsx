"use client";

import * as Sentry from "@sentry/nextjs";
import type { Route } from "next";
import { useParams, usePathname } from "next/navigation";
import { useEffect } from "react";

import { ErrorState } from "@/components/states/ErrorState";

/**
 * The workspace's error boundary (UX-011, UI-ISS-068). It sits inside the workspace layout, so a
 * page that throws while rendering is replaced in `<main>` only: the sidebar, the banners and Ask
 * stay, and the user can move on through them. Try again re-fetches and re-renders the page
 * (`retry`); Go to Home leaves it (any navigation clears the error), except on Home itself.
 * Failures above the workspace (the session, the workspace list) still reach `(app)/error.tsx`.
 * Every caught error is reported to Sentry (RG-07; the scrub rules apply).
 */
export default function WorkspaceError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const { slug } = useParams<{ slug: string }>();
  const pathname = usePathname();
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);
  const home = `/w/${slug}/home` as Route;
  return <ErrorState className="flex-1" error={error} onRetry={retry} homeHref={pathname === home ? undefined : home} />;
}
