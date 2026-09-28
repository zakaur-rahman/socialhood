import type { Platform } from "@/lib/api/types";

import { InstagramGlyph } from "./InstagramGlyph";
import { WhatsAppGlyph } from "./WhatsAppGlyph";

/** The platform's mark. Decorative: pair it with text or an aria-label. */
export function PlatformGlyph({ platform, className }: { platform: Platform; className?: string }) {
  return platform === "whatsapp" ? <WhatsAppGlyph className={className} /> : <InstagramGlyph className={className} />;
}

/** Background utility per platform (tokens --color-instagram, --color-whatsapp). */
export const PLATFORM_BG: Record<Platform, string> = { instagram: "bg-instagram", whatsapp: "bg-whatsapp" };
