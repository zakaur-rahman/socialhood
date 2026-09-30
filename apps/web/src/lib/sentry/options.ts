/**
 * Sentry options shared by the browser, Node.js and edge runtimes (T9.3, TR-OPS-01).
 *
 * No NEXT_PUBLIC_SENTRY_DSN, no Sentry: `sentryOptions()` returns null and nothing is initialised,
 * so local development, tests and builds without a DSN send nothing.
 */
import { scrubBreadcrumb, scrubEvent } from "./scrub";

export function sampleRate(raw: string | undefined): number {
  const rate = Number(raw);
  return Number.isFinite(rate) && rate >= 0 && rate <= 1 ? rate : 0;
}

export function sentryOptions() {
  // NEXT_PUBLIC_ values are inlined at build time, so each is read by its full name.
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return null;
  return {
    dsn,
    environment:
      process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NEXT_PUBLIC_VERCEL_ENV || "local",
    tracesSampleRate: sampleRate(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE),
    sendDefaultPii: false,
    beforeSend: scrubEvent,
    beforeSendTransaction: scrubEvent,
    beforeBreadcrumb: scrubBreadcrumb,
  };
}
