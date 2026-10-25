/**
 * Accent choices for the website chat widget (GR-28). The widget runs on a visitor's page, in its
 * own frame, so it can't read the app's CSS variables: the chosen colour is stored as a hex value.
 * These are the brand and platform hues; each has at least 4.5:1 contrast with white text.
 */
export const widgetAccents = [
  { name: "Blue", value: "#4467E6" },
  { name: "Teal", value: "#0F766E" },
  { name: "Green", value: "#15803D" },
  { name: "Pink", value: "#BE185D" },
  { name: "Orange", value: "#C2410C" },
  { name: "Slate", value: "#334155" },
] as const;
