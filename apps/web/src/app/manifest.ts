import type { MetadataRoute } from "next";

import { colorValue } from "@/styles/tokens";

/**
 * TR-FE-09, FR-NOT-03: the web app manifest, served at /manifest.webmanifest and linked from every
 * page. Installed, the app opens at /app (the last workspace) in its own window. The icons come
 * from scripts/generate-icons.mjs.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/app",
    name: "Social Hood",
    short_name: "Social Hood",
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
