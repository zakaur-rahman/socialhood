import path from "node:path";

import { withSentryConfig } from "@sentry/nextjs/config";
import type { NextConfig } from "next";

import { appOrigin } from "./src/lib/marketing/site";
import { securityHeaders } from "./src/lib/security/headers";

// C-145: the Docker image (apps/web/Dockerfile) builds with NEXT_OUTPUT=standalone: a self-contained
// server.js with only the node_modules it traces. Everything else (next dev, next start in the e2e
// stack, Vercel, tests) keeps the default output. Tracing starts at the monorepo root so the
// workspace packages and pnpm's store are included; Turbopack uses the same root.
const standalone = process.env.NEXT_OUTPUT === "standalone";
const monorepoRoot = path.join(__dirname, "..", "..");

// C-148: with the app on its own host (NEXT_PUBLIC_APP_URL), the public pages ship no Clerk. The
// root layout's RootAuth becomes the Clerk-free version; a layout ships every client component it
// imports, rendered or not, so the choice is a module swap at build time.
const splitHosts = appOrigin() !== null;
const turbopack: NextConfig["turbopack"] = {
  ...(standalone && { root: monorepoRoot }),
  ...(splitHosts && {
    resolveAlias: { "@/components/auth/RootAuth": "./src/components/auth/RootAuth.split.tsx" },
  }),
};

// TR-FE-07: one strict config. Never add ignoreBuildErrors or ignoreDuringBuilds.
const nextConfig: NextConfig = {
  typedRoutes: true,
  ...(standalone && { output: "standalone", outputFileTracingRoot: monorepoRoot }),
  turbopack,
  // C-143: no X-Powered-By, and no browser source maps served from the site. Sentry builds its own
  // for the upload (below) and deletes them from the output afterwards.
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  // C-161 v2: no floating "N" dev-tools button. It only ever shows under `next dev` (never in a
  // production build), but it sat over the page in every local screenshot. Next's error overlay
  // still appears for build and runtime errors.
  devIndicators: false,
  async headers() {
    return [
      // SEC-11: CSP, HSTS, framing, referrer and permissions on every route.
      { source: "/:path*", headers: securityHeaders(process.env) },
      // TR-FE-09: the service worker is always fetched fresh, so a new version reaches every
      // device. Listed after the rule above, so its own CSP wins for /sw.js.
      {
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self'" },
        ],
      },
    ];
  },
  // C-155: the site is global and in English only. The Hinglish page and the Hinglish guide were
  // taken down; their URLs move permanently (308) so links and search results still land somewhere.
  // These run before the proxy (src/proxy.ts), so the host split never sees them.
  async redirects() {
    return [
      { source: "/hi", destination: "/", permanent: true },
      { source: "/guides/replying-in-hinglish", destination: "/guides", permanent: true },
    ];
  },
  images: {
    // C-152: AVIF first (about a third smaller than WebP for the screenshots), WebP for the rest.
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      { protocol: "https", hostname: "res.cloudinary.com" },
      { protocol: "https", hostname: "**.cdninstagram.com" },
      { protocol: "https", hostname: "**.fbcdn.net" },
      { protocol: "https", hostname: "img.clerk.com" },
    ],
  },
};

// T9.3: Sentry's build step. Source maps upload (and a release is created) only when
// SENTRY_AUTH_TOKEN is set, so builds without Sentry credentials are unchanged.
const sentryUpload = Boolean(process.env.SENTRY_AUTH_TOKEN);
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  sourcemaps: { disable: !sentryUpload, deleteSourcemapsAfterUpload: true },
  release: { create: sentryUpload, finalize: sentryUpload },
  silent: !process.env.CI,
  telemetry: false,
});
