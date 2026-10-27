// Browser error tracking (T9.3). Runs before hydration. Without NEXT_PUBLIC_SENTRY_DSN nothing is
// initialised or downloaded. No Session Replay: it would record customer messages on screen (SEC-12).
// C-148: the SDK is a lazy chunk, loaded at once in the app and after idle on the public pages
// (lib/sentry/client.ts), so it is never part of a page's first-load JavaScript.
import { loadedSentry, startSentry } from "@/lib/sentry/client";

startSentry(window.location.pathname);

export function onRouterTransitionStart(href: string, navigationType: string) {
  loadedSentry()?.captureRouterTransitionStart(href, navigationType);
}
