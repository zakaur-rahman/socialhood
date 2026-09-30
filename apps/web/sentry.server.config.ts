// Sentry in the Node.js runtime, loaded by src/instrumentation.ts (T9.3).
import * as Sentry from "@sentry/nextjs";

import { sentryOptions } from "@/lib/sentry/options";

const options = sentryOptions();
if (options) Sentry.init(options);
