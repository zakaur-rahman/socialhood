/**
 * Motion values for the marketing site (C-068). They follow the UI audit's motion tokens
 * (DESIGN_SYSTEM §7: fast 120, normal 150, slow 200 ms; enter, exit and standard easings) and add
 * the slower, expressive durations the public pages may use for entrances and loops.
 */

/** cubic-bezier(0, 0, 0.2, 1): things arriving (--ease-enter). */
export const EASE_ENTER = [0, 0, 0.2, 1] as const;
/** cubic-bezier(0.4, 0, 0.2, 1): things changing in place (--ease-standard). */
export const EASE_STANDARD = [0.4, 0, 0.2, 1] as const;
/** cubic-bezier(0.16, 1, 0.3, 1): the marketing pages' expressive entrance. */
export const EASE_EXPRESSIVE = [0.16, 1, 0.3, 1] as const;

/** Seconds, as motion takes them. */
export const DURATION = {
  fast: 0.12,
  normal: 0.15,
  slow: 0.2,
  /** Marketing: a section or card entering on scroll. */
  reveal: 0.6,
  /** Marketing: a word or an illustration's step. */
  expressive: 0.45,
} as const;
