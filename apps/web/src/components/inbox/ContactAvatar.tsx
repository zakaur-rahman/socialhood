import { PLATFORM_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Avatar, AvatarBadge, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Platform } from "@/lib/api/types";
import { avatarGradient, initial } from "@/lib/inbox/format";
import { IDENTITY_FILL } from "@/lib/ui/identity";
import { cn } from "@/lib/utils";

/**
 * The Avatar primitive's sizes (`sm` 24, `default` 32, `lg` 40 px), which also size AvatarBadge.
 * 48 px (the context panel's customer card) has no size of its own: it is `lg` drawn at 48 px (on
 * the same `data-[size=lg]` variant, so it replaces `lg`'s 40 px), and its platform badge is `lg`'s
 * 16 px with a 10 px glyph, as it was. At 24 px the badge would be an 8 px dot without its glyph,
 * so the smallest avatar shows none.
 */
const SIZE = {
  48: { avatar: "lg", root: "data-[size=lg]:size-12", text: "text-lg", badge: true },
  40: { avatar: "lg", root: undefined, text: "text-base", badge: true },
  32: { avatar: "default", root: undefined, text: "text-sm", badge: true },
  24: { avatar: "sm", root: undefined, text: "text-2xs", badge: false },
} as const;

/**
 * UX-INB-04: the contact's picture, or their initial on a gradient picked by hashing the
 * contact id; a platform badge at the bottom right (replaces v1's meaningless "online" dot): the
 * Avatar primitive's AvatarBadge with the platform's fill. The gradient is the identity palette's
 * (lib/ui/identity, D-13): every stop 4.5:1 or more with the `on-brand` initial. The initial is
 * decorative, since the name is always beside the avatar, so it is hidden from screen readers.
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
    <Avatar size={s.avatar} className={cn(s.root, className)} data-testid="contact-avatar">
      {pictureUrl ? <AvatarImage src={pictureUrl} alt="" /> : null}
      <AvatarFallback
        aria-hidden
        className={cn(IDENTITY_FILL, "font-semibold", s.text, gradient)}
        data-gradient={gradient}
      >
        {initial(name)}
      </AvatarFallback>
      {platform && s.badge ? (
        <AvatarBadge className={PLATFORM_BG[platform]} data-platform={platform}>
          <PlatformGlyph platform={platform} />
        </AvatarBadge>
      ) : null}
    </Avatar>
  );
}
