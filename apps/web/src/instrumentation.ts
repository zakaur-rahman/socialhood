// Server-side error tracking (T9.3): Sentry in the Node.js and edge runtimes, and every server
// request error (Server Components, route handlers, server actions, the proxy). Without
// NEXT_PUBLIC_SENTRY_DSN nothing is initialised and captureRequestError does nothing.
import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") await import("../sentry.server.config");
  if (process.env.NEXT_RUNTIME === "edge") await import("../sentry.edge.config");
}

export const onRequestError = Sentry.captureRequestError;
