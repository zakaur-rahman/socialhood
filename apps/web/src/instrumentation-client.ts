// Browser error tracking (T9.3). Runs before hydration. Without NEXT_PUBLIC_SENTRY_DSN nothing is
// initialised. No Session Replay: it would record customer messages on screen (SEC-12).
import * as Sentry from "@sentry/nextjs";

import { sentryOptions } from "@/lib/sentry/options";

const options = sentryOptions();
if (options) Sentry.init(options);

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
