import type { Metadata, MetadataRoute } from "next";

import { SITE_NAME, appOrigin } from "@/lib/marketing/site";
import { colorValue } from "@/styles/tokens";

/** Where app/manifest.webmanifest/route.ts serves the manifest. */
export const MANIFEST_PATH = "/manifest.webmanifest";

/**
 * TR-FE-09, FR-NOT-03: the web app manifest, served at /manifest.webmanifest. Installed, the app
 * opens at /app (the last workspace) in its own window. The icons come from
 * scripts/generate-icons.mjs.
 *
 * Which pages link it (C-148): with one origin every page (the root layout), as before. With the
 * app on its own host only the dashboard's pages (app/(clerk)/layout.tsx): browsers ignore a
 * start_url on another origin than the page that links the manifest, and a public-site install
 * would open /app on the site, which redirects to the dashboard, out of the installed app's scope.
 * So the app installs from the dashboard, and the public site offers no install.
 */
export function manifestLink(app: string | null = appOrigin()): { root: Metadata; app: Metadata } {
  return app ? { root: {}, app: { manifest: MANIFEST_PATH } } : { root: { manifest: MANIFEST_PATH }, app: {} };
}

export function webManifest(): MetadataRoute.Manifest {
  return {
    id: "/app",
    name: SITE_NAME,
    short_name: SITE_NAME,
    description: "One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.",
    start_url: "/app",
    scope: "/",
    display: "standalone",
    background_color: colorValue("canvas"),
    theme_color: colorValue("canvas"),
    categories: ["business", "productivity", "social"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
