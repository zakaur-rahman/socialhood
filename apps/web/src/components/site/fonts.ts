import { Funnel_Display, Funnel_Sans } from "next/font/google";

/**
 * The public site's type (C-155): Funnel Display for headings, Funnel Sans for text, self-hosted by
 * next/font as variable fonts (one file each), swapped in when ready. Both are on screen in the first view of every public page (the
 * heading and the text beside it), so both are preloaded; the app keeps Geist (app/layout.tsx).
 * Their CSS variables go on the `.site` frame, which site.css reads.
 */
export const funnelDisplay = Funnel_Display({
  variable: "--font-funnel-display",
  subsets: ["latin"],
  display: "swap",
});

export const funnelSans = Funnel_Sans({
  variable: "--font-funnel-sans",
  subsets: ["latin"],
  display: "swap",
});

/** The classes that define the two font variables, for the `.site` frame. */
export const SITE_FONTS = `${funnelDisplay.variable} ${funnelSans.variable}`;
