/**
 * The marketing surfaces' class strings, in a module of their own so the public site's client
 * components can use them without importing primitives.tsx (and with it `cn`, Button and Link)
 * into the browser (C-152). primitives.tsx re-exports them.
 */

/**
 * The marketing card surface (C-127): `rounded-2xl` (DESIGN_SYSTEM §4), a `line` edge and the
 * `panel` fill. A card that reacts to hover adds `MARKETING_CARD_HOVER`; a card laid over the page
 * glow wears the `panel-glass` fill instead. Add padding and layout at the call site.
 */
export const MARKETING_CARD = "rounded-2xl border border-line bg-panel";
export const MARKETING_CARD_GLASS = "rounded-2xl border border-line bg-panel-glass";
export const MARKETING_CARD_HOVER = "transition-colors duration-slow hover:border-line-strong";
