/**
 * The identity palette (DESIGN_SYSTEM §1.7; owner decision D-13 option 1, C-069; UI-ISS-054,
 * UI-ISS-097). One colour per person or account, never a status or platform colour, so a customer
 * is never painted "warning" and an account ring never reads as an error. Avatar fallbacks
 * (ContactAvatar, the schedule's AccountAvatar) and the schedule's account rings and dots read it,
 * and categorical chart series should too.
 *
 * Built only from existing brand, shell and platform-blue values (no new token). The rules, with
 * WCAG contrast:
 * - every gradient stop is 4.5:1 or more with `on-brand`, the initial's colour
 *   (brand-deep 11.04, brand-strong 4.85; shell-1 6.52, shell-2 12.66; linkedin 8.72,
 *   facebook 5.17; the oklab midpoints 7.37, 9.19, 6.72);
 * - every ring and dot is 3:1 or more on `panel` (brand 4.54, brand-fg 8.23, facebook 3.19), and
 *   the rings are told apart from each other (oklab ΔE 8.9 or more; 1.42:1 or more).
 *
 * Three identities, not four: the only values in these families that reach 3:1 on panel are
 * brand-fg, brand, brand-strong and facebook, and brand-strong and facebook are 1.07:1 apart
 * (ΔE 3.0), so a fourth ring would look like the third. The initial is decorative (the name is
 * always beside the avatar), so callers render it `aria-hidden`.
 */
export type Identity = {
  /** The avatar fallback's two stops, for a 135° gradient under the initial. */
  gradient: string;
  /** The account ring around a picture or thumbnail. */
  ring: string;
  /** A solid dot (dots under 12 px are solid, never a gradient). */
  dot: string;
};

export const IDENTITIES: readonly Identity[] = [
  { gradient: "from-brand-deep to-brand-strong", ring: "ring-brand", dot: "bg-brand" },
  { gradient: "from-shell-1 to-shell-2", ring: "ring-brand-fg", dot: "bg-brand-fg" },
  { gradient: "from-linkedin to-facebook", ring: "ring-facebook", dot: "bg-facebook" },
];

/**
 * The avatar fallback's fill: the identity's gradient with the initial in `on-brand`. The palette
 * guarantees that pair, so the two come together.
 */
export const IDENTITY_FILL = "bg-linear-135 text-on-brand";

/** The n-th identity, cycling: a page that lists accounts gives each its own (UX-SCR-04). */
export function identityAt(index: number): Identity {
  const n = IDENTITIES.length;
  return IDENTITIES[((index % n) + n) % n];
}

/** A stable identity for an id: the contact id picks the pair (UX-INB-04). */
export function identityFor(id: string): Identity {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) | 0;
  return IDENTITIES[Math.abs(hash) % IDENTITIES.length];
}
