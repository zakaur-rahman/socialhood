import { dark } from "@clerk/ui/themes";

import { colorTokens } from "@/styles/tokens";

/** A colour token's value from styles/tokens.ts, for consumers that can't read CSS variables. */
function token(name: string): string {
  const found = colorTokens.find((entry) => entry.name === name);
  if (!found) throw new Error(`Unknown colour token: ${name}`);
  return found.value;
}

const BRAND_TEXT = { color: "var(--color-brand-fg)", "&:hover": { color: "var(--color-brand-fg)" } };

/**
 * Clerk's components on the §4.2 tokens (Clerk Core 3 variable names). Values are literal
 * because Clerk computes shades from them and cannot read CSS variables; the element styles below
 * are plain CSS, so they use the variables.
 *
 * Its primary is `brand-strong` (DESIGN_SYSTEM §1.4): white on `brand` is 3.63:1 (UI-ISS-005), on
 * `brand-strong` 4.85:1. Clerk also writes its links in the primary colour, where `brand-strong` is
 * 3.4:1, so links are `brand-fg`, as in the app. The account button gets the app's focus outline
 * (UI-ISS-002): Clerk's buttons set `outline: 0`.
 */
export const clerkAppearance = {
  theme: dark,
  variables: {
    colorPrimary: token("brand-strong"),
    colorPrimaryForeground: token("on-brand"),
    colorBackground: token("panel"),
    colorForeground: token("fg"),
    colorMutedForeground: token("fg-secondary"),
    colorMuted: token("field"),
    colorInput: token("field"),
    colorInputForeground: token("fg"),
    colorNeutral: token("fg"),
    colorBorder: token("line"),
    colorRing: token("brand"),
    colorDanger: token("danger"),
    colorSuccess: token("success"),
    colorWarning: token("warning"),
    colorModalBackdrop: token("scrim"),
    borderRadius: "0.5rem",
    fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    button: {
      // Solid primary buttons (Continue, Save): flat. Clerk's top shine (white 11%) took the label
      // under 4.5:1 and its hover lightens the fill (3.4:1); hover is the fill at 90%, as the
      // destructive fill's is (DESIGN_SYSTEM §8.3), so the label gets more contrast, not less.
      '&[data-variant="solid"][data-color="primary"]': {
        "&::after": { display: "none" },
        "&:hover": { backgroundColor: "color-mix(in srgb, var(--color-brand-strong) 90%, transparent)" },
      },
      // Link buttons ("Resend", "Use another method", the edit pencil) are always the primary colour.
      '&[data-variant="link"]': BRAND_TEXT,
    },
    footerActionLink: BRAND_TEXT, // "Sign up", "Sign in"
    formFieldAction: BRAND_TEXT, // "Forgot password?"
    profileSectionPrimaryButton: BRAND_TEXT, // "Add email address", "Update profile"
    menuButton: { '&[data-variant="ghost"][data-color="primary"]': BRAND_TEXT }, // "Connect account", "Add two-step verification"
    formButtonReset: BRAND_TEXT, // "Cancel" beside a form's primary button
    // The account modal's current page (Account, Security) is drawn in the primary colour too.
    navbarButton: { '&[data-color="primary"]': BRAND_TEXT },
    // The account modal's "Primary" badge: Clerk derives its text from `colorBorder`, which gave
    // 1.19:1. Brand-fg text on the brand-soft fill is well over 4.5:1.
    badge: {
      color: "var(--color-fg-secondary)", // the neutral badges ("Primary", "Unverified") share the bad derivation
      '&[data-color="primary"]': {
        color: "var(--color-brand-fg)",
        backgroundColor: "var(--color-brand-soft)",
        borderColor: "var(--color-brand-line)",
      },
    },
    // The global :focus-visible outline (globals.css), restated: Clerk's own styles set outline 0.
    userButtonTrigger: {
      "&:focus-visible": {
        outline: "2px solid var(--color-brand)",
        outlineOffset: "2px",
        boxShadow: "none",
      },
    },
  },
} as const;
