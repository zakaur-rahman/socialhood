import { dark } from "@clerk/ui/themes";

/**
 * Clerk's components on the §4.2 tokens (Clerk Core 3 variable names). Values are literal
 * because Clerk computes shades from them and cannot read CSS variables.
 */
export const clerkAppearance = {
  theme: dark,
  variables: {
    colorPrimary: "#567FF8",
    colorPrimaryForeground: "#FFFFFF",
    colorBackground: "#1F1F1F",
    colorForeground: "#FFFFFF",
    colorMutedForeground: "#9B9CA0",
    colorMuted: "#1D1D1D",
    colorInput: "#1D1D1D",
    colorInputForeground: "#FFFFFF",
    colorNeutral: "#FFFFFF",
    colorBorder: "rgb(255 255 255 / 0.10)",
    colorRing: "#567FF8",
    colorDanger: "#EF4444",
    colorSuccess: "#22C55E",
    colorWarning: "#FB923C",
    colorModalBackdrop: "rgb(0 0 0 / 0.6)",
    borderRadius: "0.5rem",
    fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
  },
} as const;
