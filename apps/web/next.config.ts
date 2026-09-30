import type { NextConfig } from "next";

// TR-FE-07: one strict config. Never add ignoreBuildErrors or ignoreDuringBuilds.
const nextConfig: NextConfig = {
  typedRoutes: true,
  poweredByHeader: false,
  // TR-FE-09: the service worker is always fetched fresh, so a new version reaches every device.
  async headers() {
    return [
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
