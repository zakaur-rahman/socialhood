/**
 * SEC-12: what the web app sends to Sentry carries no PII or secrets. The same rules as the API
 * (apps/api/src/socialhood/observability/sentry.py):
 *
 * - the request keeps only its method and its URL without the query string: no headers, cookies
 *   or body;
 * - the user keeps only an id;
 * - free-text fields (text, body, caption…) are dropped by name, secret-looking keys are redacted,
 *   and emails, bearer tokens, JWTs and long token-like strings are masked in any text;
 * - breadcrumb and span URLs lose their query strings.
 *
 * Session Replay is never enabled: it would record customer messages on screen.
 */
import type { Breadcrumb, Event } from "@sentry/nextjs";

export const REDACTED = "[redacted]";

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const BEARER = /\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+/gi;
const JWT = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/g;
// 40+ characters mixing letters and digits: tokens, keys, signatures. UUIDs (36) stay readable.
const LONG_TOKEN =
  /(^|[^A-Za-z0-9_-])((?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{40,})(?![A-Za-z0-9_-])/g;
const QUERY = /\?[^\s"'#]*/g;

const TEXT_KEYS = new Set([
  "text",
  "body",
  "caption",
  "content",
  "contents",
  "prompt",
  "reply",
  "message_text",
  "comment_text",
  "first_comment",
  "email",
  "phone",
  "raw",
  "payload",
  "data",
]);
const SECRET_KEY =
  /token|secret|authorization|password|signature|cookie|session|dsn|api_?key|(?:^|_)code$/i;
const SAFE_KEYS = new Set(["status_code", "error_code", "platform_code", "http_status_code"]);
const SAFE_CONTEXTS = new Set([
  "trace",
  "runtime",
  "os",
  "device",
  "app",
  "browser",
  "culture",
  "response",
  "cloud_resource",
]);

export function scrubText(value: string): string {
  return value
    .replace(EMAIL, "[email]")
    .replace(BEARER, "$1 [redacted]")
    .replace(JWT, "[jwt]")
    .replace(LONG_TOKEN, "$1[token]");
}

export function stripQuery(url: string): string {
  return url.replace(QUERY, "");
}

function isSecretKey(key: string): boolean {
  return !SAFE_KEYS.has(key.toLowerCase()) && SECRET_KEY.test(key);
}

/** Drop content keys, redact secret keys and mask text, recursively. */
export function scrubValue(value: unknown): unknown {
  if (typeof value === "string") return scrubText(value);
  if (Array.isArray(value)) return value.map(scrubValue);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      if (TEXT_KEYS.has(key.toLowerCase())) continue;
      out[key] = isSecretKey(key) ? REDACTED : scrubValue(item);
    }
    return out;
  }
  return value;
}

function scrubUrlFields(data: Record<string, unknown>): Record<string, unknown> {
  const out = { ...data };
  delete out["http.query"];
  delete out["http.fragment"];
  for (const key of ["url", "http.url", "from", "to"]) {
    const value = out[key];
    if (typeof value === "string") out[key] = stripQuery(value);
  }
  return out;
}

export function scrubBreadcrumb(crumb: Breadcrumb): Breadcrumb {
  if (crumb.message) crumb.message = scrubText(stripQuery(crumb.message));
  if (crumb.data) crumb.data = scrubValue(scrubUrlFields(crumb.data)) as Breadcrumb["data"];
  return crumb;
}

/** beforeSend and beforeSendTransaction. */
export function scrubEvent<T extends Event>(event: T): T {
  if (event.request) {
    const { method, url } = event.request;
    event.request = { method, url: url ? stripQuery(url) : undefined };
  }
  if (event.user) event.user = event.user.id ? { id: event.user.id } : {};
  if (event.message) event.message = scrubText(event.message);
  for (const exception of event.exception?.values ?? []) {
    if (exception.value) exception.value = scrubText(exception.value);
    for (const frame of exception.stacktrace?.frames ?? []) delete frame.vars;
  }
  if (event.breadcrumbs) event.breadcrumbs = event.breadcrumbs.map(scrubBreadcrumb);
  if (event.extra) event.extra = scrubValue(event.extra) as Event["extra"];
  if (event.contexts) {
    for (const [name, block] of Object.entries(event.contexts)) {
      if (!SAFE_CONTEXTS.has(name)) event.contexts[name] = scrubValue(block) as typeof block;
    }
  }
  for (const span of event.spans ?? []) {
    if (span.description) span.description = scrubText(stripQuery(span.description));
    if (span.data) span.data = scrubValue(scrubUrlFields(span.data)) as typeof span.data;
  }
  return event;
}
