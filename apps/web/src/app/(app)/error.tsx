"use client";

import { ErrorState } from "@/components/states/ErrorState";

/** Route-level error boundary for signed-in pages: explain and offer Retry, never redirect. */
export default function SignedInError({ error, reset }: { error: Error; reset: () => void }) {
  return <ErrorState fullPage error={error} onRetry={reset} />;
}
