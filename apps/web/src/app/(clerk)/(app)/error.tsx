"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

import { ErrorState } from "@/components/states/ErrorState";

/**
 * Route-level error boundary for signed-in pages: report it (RG-07; the Sentry scrub rules apply),
 * explain and offer Retry, never redirect.
 */
export default function SignedInError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);
  return <ErrorState fullPage error={error} onRetry={reset} />;
}
