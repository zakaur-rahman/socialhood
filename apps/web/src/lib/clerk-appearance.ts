import { dark } from "@clerk/ui/themes";

import { colorValue as token, radiusValue as radius, type Theme } from "@/styles/tokens";

const BRAND_TEXT = { color: "var(--color-brand-fg)", "&:hover": { color: "var(--color-brand-fg)" } };

/**
 * Clerk's components on the §4.2 tokens (Clerk Core 3 variable names). Values are literal
 * (read from the generated tokens, so globals.css stays the only place they are written)
 * because Clerk computes shades from them and cannot read CSS variables, so they are per theme
 * (C-129): `clerkAppearanceFor("light")` reads the light values and drops Clerk's dark base. The
 * root layout carries the dark values; the components that render Clerk's UI (the sign-in and
 * sign-up cards, the user button) pass the set for the theme on screen (ThemedClerk). The
 * element styles below are plain CSS, so they use the variables (which follow the theme by
 * themselves), the brand gradient and the radii included.
 *
 * Its primary is `brand-strong` (DESIGN_SYSTEM §1.4): white on `brand` is 4.17:1 (UI-ISS-005), on
 * `brand-strong` 5.82:1. Clerk also writes its links in the primary colour, where `brand-strong` is
 * 2.85:1, so links are `brand-fg`, as in the app. The account button gets the app's focus outline
 * (UI-ISS-002): Clerk's buttons set `outline: 0`.
 */
function appearanceWithoutBase(theme: Theme) {
  const t = (name: string) => token(name, theme);
  return {
    variables: {
      colorPrimary: t("brand-strong"),
      colorPrimaryForeground: t("on-brand"),
      colorBackground: t("panel"),
      colorForeground: t("fg"),
      colorMutedForeground: t("fg-secondary"),
      colorMuted: t("field"),
      colorInput: t("field"),
      colorInputForeground: t("fg"),
      colorNeutral: t("fg"),
      colorBorder: t("line"),
      colorRing: t("brand"),
      colorDanger: t("danger"),
      colorSuccess: t("success"),
      colorWarning: t("warning"),
      colorModalBackdrop: t("scrim"),
      borderRadius: radius("lg"),
      fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
    },
    elements: {
      button: {
        // Solid primary buttons (Continue, Save): flat. Clerk's top shine (white 11%) took the label
        // to 4.67:1 and its hover lightens the fill; hover is the fill at 90%, as the
        // destructive fill's is (DESIGN_SYSTEM §8.3), so the label gets more contrast, not less.
        // They wear the app's primary: the brand gradient (Button `default`), brighter on hover.
        '&[data-variant="solid"][data-color="primary"]': {
          backgroundImage: "var(--gradient-brand)",
          color: "var(--color-on-brand)",
          boxShadow: "none",
          "&::after": { display: "none" },
          "&:hover": { filter: "brightness(1.1)" },
          "&:active": { filter: "brightness(0.95)" },
        },
        // Outline buttons ("Add", "Cancel"): the app's control edge and hover fill. Clerk draws its
        // own edges as a near-invisible 1% box shadow with `border-width: 0`, and its internal rules
        // outrank these, so the edges in this file are !important.
        '&[data-variant="outline"]': {
          border: "1px solid var(--color-line-control) !important",
          backgroundColor: "transparent",
          boxShadow: "none !important",
          "&:hover": { backgroundColor: "var(--color-hover)" },
        },
        // Link buttons ("Resend", "Use another method", the edit pencil) are always the primary colour.
        '&[data-variant="link"]': BRAND_TEXT,
      },
      // Surfaces, as the app draws its cards: one `panel` surface with a crisp `line` edge and
      // `rounded-xl`. The inner card and the footer sit on it transparently, so there is one edge,
      // not two. The user menu and the account modal float on `overlay` (D-12).
      cardBox: {
        // Every rule and edge Clerk draws inside its surfaces (dividers between rows, the footer
        // line, section rules) takes the app's border colour: Clerk's own is a faint neutral alpha
        // that vanished on light. Recoloured only: no border is added where Clerk draws none.
        "& *": { borderColor: "var(--color-line) !important" },
        backgroundColor: "var(--color-panel)",
        border: "1px solid var(--color-line) !important",
        borderRadius: "var(--radius-xl)",
        boxShadow: "var(--shadow-overlay) !important",
      },
      card: { backgroundColor: "transparent", border: "0 !important", borderRadius: "0", boxShadow: "none !important" },
      footer: {
        background: "transparent !important",
        borderTop: "1px solid var(--color-line) !important",
        // "Secured by" (Clerk's branding line, an unnamed `<p data-variant="buttonSmall"
        // data-color="inherit">`): Clerk fades it from the foreground, which axe measured below
        // 4.5:1 at 375 and 1280 px. Solid `fg-secondary`, as the app's quiet text is (C-135).
        '& p[data-variant="buttonSmall"][data-color="inherit"]': {
          color: "var(--color-fg-secondary) !important",
          opacity: "1 !important",
        },
        // A development instance paints an orange bar behind "Secured by" and "Development mode"
        // (absolute `div`s, first in the footer item), where no text colour can pass 4.5:1. The bar
        // is made transparent, so the text sits on the panel; a production instance has none.
        '& [class*="cl-footerItem"] > div:first-child, & [class*="cl-footerItem"] > div:first-child *': {
          backgroundColor: "transparent !important",
        },
      },
      userButtonPopoverCard: {
        "& *": { borderColor: "var(--color-line) !important" },
        backgroundColor: "var(--color-overlay) !important",
        border: "1px solid var(--color-line) !important",
        borderRadius: "var(--radius-xl)",
        boxShadow: "var(--shadow-floating) !important",
      },
      userButtonPopoverMain: { backgroundColor: "var(--color-overlay)" },
      userButtonPopoverFooter: {
        background: "var(--color-overlay) !important",
        borderTop: "1px solid var(--color-line) !important",
      },
      modalContent: {
        "& *": { borderColor: "var(--color-line) !important" },
        borderRadius: "var(--radius-xl)",
        border: "1px solid var(--color-line) !important",
      },
      navbar: { backgroundColor: "var(--color-panel)", borderRight: "1px solid var(--color-line) !important" },
      scrollBox: { backgroundColor: "var(--color-overlay)" },
      dividerLine: { backgroundColor: "var(--color-line)" },
      // The account modal's section rules (Profile, Email addresses, Phone numbers, Connected
      // accounts) and the page header's underline: Clerk draws them from a faint neutral alpha that
      // vanished on light. Recoloured to `line`, never added where Clerk draws none.
      profileSection: { borderColor: "var(--color-line) !important" },
      profileSectionContent: { borderColor: "var(--color-line) !important" },
      profileSectionItemList: { borderColor: "var(--color-line) !important" },
      header: { borderColor: "var(--color-line) !important" },
      pageScrollBox: { borderColor: "var(--color-line) !important" },
      // Fields, on the app's field recipe: `field` fill, the 40% control edge, `rounded-lg`, and the
      // brand edge on a raised fill when focused.
      formFieldInput: {
        backgroundColor: "var(--color-field)",
        border: "1px solid var(--color-line-control) !important",
        borderRadius: "var(--radius-lg)",
        boxShadow: "none !important",
        "&:focus, &:focus-visible": {
          borderColor: "var(--color-brand) !important",
          backgroundColor: "var(--color-raised)",
        },
      },
      socialButtonsBlockButton: {
        border: "1px solid var(--color-line-control) !important",
        backgroundColor: "transparent",
        boxShadow: "none !important",
        "&:hover": { backgroundColor: "var(--color-hover)" },
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
}

/**
 * The appearance for one theme. Dark adds Clerk's own dark base theme; Light uses Clerk's default
 * base with every variable above set. The Clerk components pass it (components/auth/ThemedClerk).
 */
export function clerkAppearanceFor(theme: Theme) {
  const appearance = appearanceWithoutBase(theme);
  return theme === "dark" ? { theme: dark, ...appearance } : appearance;
}

/**
 * The provider's appearance in the root layout: the dark values and the element styles, with no
 * base theme, because the base is per component and per theme (above). Clerk merges a component's
 * appearance over it.
 */
export const clerkAppearance = appearanceWithoutBase("dark");

/**
 * The sign-in and sign-up card (C-158), merged over the provider's appearance by ThemedClerk: layout,
 * type and the states the card needs on top of the app-wide recipe above. It lives here, not in the
 * page shell, so the client bundle that renders Clerk doesn't pull in the server shell's imports.
 *
 * - **One logo per page:** Clerk's in-card logo is off; the shell shows the mark (the night panel on
 *   wide screens, the bar above the card below `lg`). The card's title stays the page's only h1.
 * - **The public site's language:** the title in Geist 700 with tight tracking, left-aligned like the
 *   site's headings; a flat ink button (the site's primary: `fg` on `canvas`, so a near-white button
 *   in Dark and a near-black one in Light) instead of the brand gradient; no arrow; no shadow at rest
 *   (the card sits on the canvas with its `line` edge).
 * - **Accessibility:** Clerk sets `outline: 0` on its controls, so the app's focus outline (2px
 *   `brand`, 2px offset, as globals.css) is restated on every link, button and checkbox in the card.
 *   Controls are 44 px tall. The legal-consent checkbox (Clerk's "Require express consent", rendered
 *   as `formFieldCheckboxInput` and `formFieldCheckboxLabel` in @clerk/ui 1.38) gets a 16 px box with
 *   the 3:1 control edge, and its links are `brand-fg` with an underline (Clerk's primary was 2.9:1
 *   on the dark panel). Field errors are `danger-fg`.
 */
const FOCUS_RING = {
  outline: "2px solid var(--color-brand) !important",
  outlineOffset: "2px",
};

export const authCardAppearance = {
  options: {
    logoPlacement: "none",
    socialButtonsVariant: "blockButton",
  },
  elements: {
    rootBox: { width: "100%" },
    cardBox: {
      width: "100%",
      maxWidth: "100%",
      boxShadow: "none !important",
      "& :is(a, button, input[type=checkbox]):focus-visible": FOCUS_RING,
    },
    // A phone keeps 24 px inside the card, not Clerk's 40, so the fields stay wide at 375.
    card: { "@media (max-width: 30rem)": { paddingInline: "1.5rem" } },
    header: { alignItems: "flex-start", textAlign: "left" },
    headerTitle: {
      fontSize: "1.25rem",
      lineHeight: "1.2",
      fontWeight: 700,
      letterSpacing: "-0.02em",
      textAlign: "left",
    },
    headerSubtitle: { fontSize: "0.9375rem", color: "var(--color-fg-secondary)", textAlign: "left" },
    socialButtonsBlockButton: { minHeight: "2.75rem" },
    socialButtonsBlockButtonText: { color: "var(--color-fg)", fontSize: "0.9375rem", fontWeight: 500 },
    dividerText: { color: "var(--color-fg-secondary)" },
    formFieldLabel: { fontWeight: 500 },
    formFieldInput: { minHeight: "2.75rem", fontSize: "0.9375rem" },
    formFieldErrorText: { color: "var(--color-danger-fg)" },
    formButtonPrimary: {
      width: "100%",
      minHeight: "2.75rem",
      fontSize: "0.9375rem",
      fontWeight: 600,
      backgroundImage: "none !important",
      backgroundColor: "var(--color-fg) !important",
      color: "var(--color-canvas) !important",
      // Hover lifts the ink a step toward the canvas (the site's .btn-main does the same with a mix).
      "&:hover": { opacity: 0.88, filter: "none !important" },
      "&:active": { filter: "none !important" },
    },
    buttonArrowIcon: { display: "none" },
    formFieldCheckboxInput: {
      width: "1rem",
      height: "1rem",
      marginTop: "0.125rem",
      borderRadius: "var(--radius-sm)",
      accentColor: "var(--color-brand-strong)",
      // The 3:1 control edge, drawn as an outline so the focus outline above replaces it.
      boxShadow: "none !important",
      outline: "1px solid var(--color-line-control)",
    },
    formFieldCheckboxLabel: {
      color: "var(--color-fg-secondary)",
      fontSize: "0.875rem",
      lineHeight: "1.45",
      "& a": {
        color: "var(--color-brand-fg) !important",
        textDecoration: "underline",
        textUnderlineOffset: "3px",
      },
      "& a:hover": { color: "var(--color-fg) !important" },
    },
    footerActionText: { color: "var(--color-fg-secondary)" },
  },
} as const;
