import type { NextConfig } from "next";

import { securityHeaders } from "./src/lib/security/headers";

// TR-FE-07: one strict config. Never add ignoreBuildErrors or ignoreDuringBuilds.
const nextConfig: NextConfig = {
  typedRoutes: true,
  poweredByHeader: false,
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
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "res.cloudinary.com" },
      { protocol: "https", hostname: "**.cdninstagram.com" },
      { protocol: "https", hostname: "**.fbcdn.net" },
      { protocol: "https", hostname: "img.clerk.com" },
    ],
  },
};

export default nextConfig;
