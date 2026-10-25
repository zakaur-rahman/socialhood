import type { Platform } from "@/lib/api/types";

import { FacebookGlyph } from "./FacebookGlyph";
import { InstagramGlyph } from "./InstagramGlyph";
import { WebGlyph } from "./WebGlyph";
import { WhatsAppGlyph } from "./WhatsAppGlyph";

/** The platform's mark. Decorative: pair it with text or an aria-label. */
export function PlatformGlyph({ platform, className }: { platform: Platform; className?: string }) {
  if (platform === "web") return <WebGlyph className={className} />;
  if (platform === "whatsapp") return <WhatsAppGlyph className={className} />;
  if (platform === "facebook") return <FacebookGlyph className={className} />;
  return <InstagramGlyph className={className} />;
}

/**
 * The platforms' own logo colours (C-135), for a badge or tile that holds the glyph alone. They are
 * lighter than `PLATFORM_BG`, so never put text on them (the darkened fills below pass 4.5:1).
 */
export const PLATFORM_LOGO_BG: Record<Platform, string> = {
  instagram: "bg-instagram-logo-gradient",
  whatsapp: "bg-whatsapp-logo",
  facebook: "bg-facebook-logo",
  web: "bg-web",
};

/** Background utility per platform, for fills with text on them (tokens --color-instagram, --color-whatsapp, --color-facebook, --color-web). */
export const PLATFORM_BG: Record<Platform, string> = {
  instagram: "bg-instagram",
  whatsapp: "bg-whatsapp",
  facebook: "bg-facebook",
  web: "bg-web",
};
