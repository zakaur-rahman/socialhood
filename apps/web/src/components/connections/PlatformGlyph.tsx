import type { Platform } from "@/lib/api/types";

import { FacebookGlyph } from "./FacebookGlyph";
import { InstagramGlyph } from "./InstagramGlyph";
import { WebGlyph } from "./WebGlyph";
import { WhatsAppGlyph } from "./WhatsAppGlyph";
import { YouTubeGlyph } from "./YouTubeGlyph";

/** The platform's mark. Decorative: pair it with text or an aria-label. */
export function PlatformGlyph({ platform, className }: { platform: Platform; className?: string }) {
  if (platform === "web") return <WebGlyph className={className} />;
  if (platform === "whatsapp") return <WhatsAppGlyph className={className} />;
  if (platform === "facebook") return <FacebookGlyph className={className} />;
  if (platform === "youtube") return <YouTubeGlyph className={className} />;
  return <InstagramGlyph className={className} />;
}

/**
 * The platforms' own logo colours (C-135), for a badge or tile that holds the glyph alone. They are
 * lighter than the platform fill tokens, so never put text on them.
 */
export const PLATFORM_LOGO_BG: Record<Platform, string> = {
  instagram: "bg-instagram-logo-gradient",
  whatsapp: "bg-whatsapp-logo",
  facebook: "bg-facebook-logo",
  web: "bg-web",
  youtube: "bg-youtube-logo",
};
