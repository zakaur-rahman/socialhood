import { webManifest } from "@/lib/pwa/manifest";

// The web app manifest (TR-FE-09), built once at build time. A route rather than app/manifest.ts,
// whose link Next adds to every page: which pages link it depends on the hosts (C-148).
export const dynamic = "force-static";

export function GET() {
  return new Response(JSON.stringify(webManifest()), {
    headers: { "Content-Type": "application/manifest+json" },
  });
}
