/**
 * SEC-11: the web app's response headers, applied to every route by next.config.ts.
 *
 * The CSP allows only the app itself, Clerk (its Frontend API, images, bot protection and
 * telemetry), Cloudinary (uploads and delivery), Instagram's and Facebook's CDNs (profile pictures
 * and platform media), Meta's SDK (WhatsApp Embedded Signup), Sentry (the DSN's host) and the API.
 * Hosts that depend on the environment are read from the NEXT_PUBLIC_* variables at build time.
 *
 * Meta's SDK is allowed app-wide although only Settings → Connections loads it: a CSP belongs to
 * the document, and App Router navigations keep the document, so a per-page CSP would block the
 * SDK after an in-app navigation. Scripts keep 'unsafe-inline' because Next.js bootstraps with
 * inline scripts; a nonce would make every page dynamic. Nothing renders user or model content as
 * HTML (React escapes it), which is what the CSP backs up.
 */

type Env = Record<string, string | undefined>;

/** "https://host[:port]" of a URL, or null when it isn't one. */
export function originOf(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.origin : null;
  } catch {
    return null;
  }
}

/** Clerk's Frontend API host, which the publishable key encodes: pk_{env}_{base64("host$")}. */
export function clerkFrontendApi(publishableKey: string | undefined): string | null {
  const encoded = publishableKey?.split("_")[2];
  if (!encoded) return null;
  try {
    const host = atob(encoded).replace(/\$$/, "");
    return /^[a-z0-9.-]+$/i.test(host) ? `https://${host}` : null;
  } catch {
    return null;
  }
}

export function contentSecurityPolicy(env: Env): string {
  const dev = env.NODE_ENV !== "production";
  const api = originOf(env.NEXT_PUBLIC_API_BASE_URL);
  const clerk = clerkFrontendApi(env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  const sentry = originOf(env.NEXT_PUBLIC_SENTRY_DSN);
  const clerkProtect = "https://*.protect.clerk.com";
  const platformMedia = ["https://*.cdninstagram.com", "https://*.fbcdn.net", "https://*.fbsbx.com"];

  const directives: Record<string, (string | null | false)[]> = {
    "default-src": ["'self'"],
    "script-src": [
      "'self'",
      "'unsafe-inline'",
      dev && "'unsafe-eval'", // React's development build
      clerk,
      "https://challenges.cloudflare.com",
      clerkProtect,
      "https://connect.facebook.net",
    ],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "blob:", "data:", "https://res.cloudinary.com", "https://img.clerk.com", ...platformMedia],
    "media-src": ["'self'", "blob:", "https://res.cloudinary.com", ...platformMedia],
    "font-src": ["'self'"],
    "connect-src": [
      "'self'",
      api,
      clerk,
      "https://clerk-telemetry.com",
      "https://*.clerk-telemetry.com",
      clerkProtect,
      "https://api.cloudinary.com",
      "https://res.cloudinary.com",
      sentry,
      "https://*.facebook.com",
    ],
    "frame-src": ["'self'", "https://challenges.cloudflare.com", clerkProtect, "https://*.facebook.com"],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  const parts = Object.entries(directives).map(([name, values]) =>
    [name, ...new Set(values.filter((value): value is string => Boolean(value)))].join(" "),
  );
  // Only where the API is https too: a local production build talks to http://localhost.
  if (!dev && api?.startsWith("https://")) parts.push("upgrade-insecure-requests");
  return parts.join("; ");
}

export function securityHeaders(env: Env): { key: string; value: string }[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(env) },
    { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    {
      key: "Permissions-Policy",
      value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    },
    // Meta's Embedded Signup popup reports back to this window, so popups keep their opener.
    { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  ];
}
