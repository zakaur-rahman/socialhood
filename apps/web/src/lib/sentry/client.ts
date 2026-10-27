/**
 * The browser's Sentry, loaded on demand (C-148). `@sentry/nextjs` is only ever imported
 * dynamically here, so it is a chunk of its own and never part of a page's first load:
 *
 * - without NEXT_PUBLIC_SENTRY_DSN nothing is downloaded at all;
 * - in the signed-in app instrumentation-client.ts starts loading it straight away;
 * - on the public pages it loads once the page is idle, or at the first error before then.
 *
 * The app's own error boundaries import Sentry directly; it is the same module instance.
 */
import { sentryOptions } from "./options";

type SentryModule = typeof import("@sentry/nextjs");

let loading: Promise<SentryModule | null> | null = null;
let loaded: SentryModule | null = null;

/** Download and initialise the SDK once. Null without a DSN, or if the chunk fails to load. */
export function loadSentry(): Promise<SentryModule | null> {
  if (!loading) {
    const options = sentryOptions();
    loading = options
      ? import("@sentry/nextjs").then(
          (Sentry) => {
            Sentry.init(options);
            loaded = Sentry;
            return Sentry;
          },
          () => null,
        )
      : Promise.resolve(null);
  }
  return loading;
}

/** The SDK if it has finished loading, for calls that only matter once it runs (navigation spans). */
export function loadedSentry(): SentryModule | null {
  return loaded;
}

/** Report an error, loading the SDK first if needed. Does nothing without a DSN. */
export function captureError(error: unknown): void {
  void loadSentry().then((Sentry) => Sentry?.captureException(error));
}

/** The signed-in app's paths, where Sentry starts loading at once. */
export const APP_PATH = /^\/(?:app|w)(?:\/|$)/;

/**
 * Start Sentry for the page at `pathname`: at once in the app; on a public page when the browser
 * is idle (at most `timeout` ms later), reporting any error that happens before then.
 */
export function startSentry(pathname: string, timeout = 4000): void {
  if (!sentryOptions()) return;
  if (APP_PATH.test(pathname)) {
    void loadSentry();
    return;
  }
  let started = false;
  const early = (event: ErrorEvent | PromiseRejectionEvent) => {
    captureError("reason" in event ? event.reason : (event.error ?? event.message));
    start();
  };
  const start = () => {
    if (started) return;
    started = true;
    // Once the SDK runs, its own handlers take over.
    void loadSentry().then(() => {
      window.removeEventListener("error", early);
      window.removeEventListener("unhandledrejection", early);
    });
  };
  window.addEventListener("error", early);
  window.addEventListener("unhandledrejection", early);
  if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(start, { timeout });
  else window.setTimeout(start, timeout);
}

/** For tests: forget the loaded SDK. */
export function resetSentryForTests(): void {
  loading = null;
  loaded = null;
}
