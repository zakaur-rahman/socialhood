import { renderOgImage } from "@/components/marketing/og";

// Drawn once at build time. One stable URL (/og.png) that every public page's Open Graph and
// Twitter metadata names: a page that sets its own openGraph would drop a file-convention image
// inherited from the layout.
export const dynamic = "force-static";

export function GET() {
  return renderOgImage();
}
