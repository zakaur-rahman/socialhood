import { PLATFORM_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Platform } from "@/lib/api/types";
import { avatarGradient, initial } from "@/lib/inbox/format";
import { IDENTITY_FILL } from "@/lib/ui/identity";
import { cn } from "@/lib/utils";

const SIZE = {
  48: { root: "size-12", text: "text-lg", badge: "size-4", glyph: "size-2.5" },
  40: { root: "size-10", text: "text-base", badge: "size-4", glyph: "size-2.5" },
  32: { root: "size-8", text: "text-sm", badge: "size-3.5", glyph: "size-2" },
  24: { root: "size-6", text: "text-2xs", badge: "", glyph: "" },
} as const;

/**
 * UX-INB-04: the contact's picture, or their initial on a gradient picked by hashing the
 * contact id; a platform badge at the bottom right (replaces v1's meaningless "online" dot).
 * The gradient is the identity palette's (lib/ui/identity, D-13): every stop 4.5:1 or more with
 * the `on-brand` initial. The initial is decorative, since the name is always beside the avatar,
 * so it is hidden from screen readers.
 */
export function ContactAvatar({
  id,
  name,
  pictureUrl,
  platform,
  size = 48,
  className,
}: {
  id: string;
  name: string;
  pictureUrl?: string | null;
  /** Shows the platform badge. */
  platform?: Platform;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  const s = SIZE[size];
  const gradient = avatarGradient(id);
  return (
    <span className={cn("relative inline-flex shrink-0", className)} data-testid="contact-avatar">
      <Avatar className={s.root}>
        {pictureUrl ? <AvatarImage src={pictureUrl} alt="" /> : null}
        <AvatarFallback
          aria-hidden
          className={cn(IDENTITY_FILL, "font-semibold", s.text, gradient)}
          data-gradient={gradient}
        >
          {initial(name)}
        </AvatarFallback>
      </Avatar>
      {platform && s.badge ? (
        <span
          className={cn(
            "absolute -right-0.5 -bottom-0.5 grid place-items-center rounded-full border-2 border-panel text-on-brand",
            s.badge,
            PLATFORM_BG[platform],
          )}
          data-platform={platform}
        >
          <PlatformGlyph platform={platform} className={s.glyph} />
        </span>
      ) : null}
    </span>
  );
}
