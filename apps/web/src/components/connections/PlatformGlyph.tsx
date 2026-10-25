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

/** Background utility per platform (tokens --color-instagram, --color-whatsapp, --color-facebook, --color-web). */
export const PLATFORM_BG: Record<Platform, string> = {
  instagram: "bg-instagram",
  whatsapp: "bg-whatsapp",
  facebook: "bg-facebook",
  web: "bg-web",
};
