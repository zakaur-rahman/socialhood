/**
 * The landing page's example data (C-155): a made-up shop and a made-up creator, with neutral names,
 * cities and dollar prices. The words come from the site's own copy (the FAQ, the feature cards, the
 * old illustrations' examples); nothing here is a customer or a real figure. The scenes say they
 * are examples. Shared by the server markup and the motion script (landing-motion.ts), so the
 * moving scenes play the same messages the still frame shows.
 */

/**
 * Where a message came from: the mark colour (a site.css variable) and its label. The three channel
 * colours are the page's one graphic motif (C-157): a comment is Instagram's colour drawn as a ring,
 * not a second pink.
 */
export const SOURCES = {
  dm: { label: "Instagram DM", colour: "var(--ig)" },
  comment: { label: "Comment on your Reel", colour: "var(--ig)" },
  whatsapp: { label: "WhatsApp", colour: "var(--wa)" },
  web: { label: "Website chat", colour: "var(--web)" },
} as const;

export type SourceKey = keyof typeof SOURCES;

/** The three channels, in the motif's order: Instagram, WhatsApp, website chat. */
export const CHANNELS = ["dm", "whatsapp", "web"] as const satisfies readonly SourceKey[];
/** A chip's tone: the site's tag classes. */
export type Tone = "need" | "draft" | "ok" | "stop" | "plain";

export type HeroNote = { source: SourceKey; name: string; text: string; ago: string; tag: string; tone: Tone };

/** The hero's inbox, sorted as the inbox sorts it: what needs a person first. */
export const HERO_NOTES: HeroNote[] = [
  { source: "dm", name: "Sam K.", text: "Can I talk to a person, please?", ago: "9m", tag: "Needs you", tone: "need" },
  { source: "whatsapp", name: "Leo M.", text: "My order arrived damaged", ago: "31m", tag: "Needs you", tone: "need" },
  { source: "dm", name: "Maya R.", text: "Is the linen shirt in M?", ago: "2m", tag: "AI draft", tone: "draft" },
  { source: "whatsapp", name: "Nina", text: "What time do you open on Sunday?", ago: "26m", tag: "AI draft", tone: "draft" },
  { source: "dm", name: "Theo", text: "Do you deliver to Toronto?", ago: "12m", tag: "AI draft", tone: "draft" },
  { source: "web", name: "Visitor", text: "Do you take bulk orders?", ago: "5m", tag: "Lead", tone: "ok" },
  { source: "comment", name: "ana.wears", text: "LINK", ago: "6m", tag: "Sent by DM", tone: "ok" },
  { source: "comment", name: "k.promo", text: "Follow my page for free followers", ago: "21m", tag: "Spam", tone: "stop" },
];

/**
 * Where each hero message lies in the scattered pile before the inbox sorts it (C-157 motion), by
 * row: x and y as percentages of the message's own box (so the pile scales with the inbox at every
 * width, and the server can draw it with no measuring), and a tilt in degrees. The rows land in a
 * loose heap over the inbox's own area, out of order.
 */
export const HERO_PILE: { x: number; y: number; r: number }[] = [
  { x: -9, y: 320, r: -6 },
  { x: 11, y: -40, r: 4 },
  { x: 6, y: 340, r: 7 },
  { x: -13, y: -120, r: -3 },
  { x: 12, y: 30, r: -5 },
  { x: 3, y: -260, r: 3 },
  { x: -7, y: 20, r: 5 },
  { x: 9, y: -590, r: -7 },
];

/** The shop's knowledge in the "how it works" scene; `cite` marks the lines the draft uses. */
export const KNOWLEDGE: { title: string; lines: { text: string; right?: string; cite?: "a" | "b" | "c" }[] }[] = [
  {
    title: "Price list",
    lines: [
      { text: "Linen shirt · Blue, White, Sage · S to XL", right: "$39", cite: "a" },
      { text: "Denim jacket · M, L", right: "$79" },
      { text: "Cotton scarf · One size", right: "$19" },
    ],
  },
  {
    title: "Delivery FAQ",
    lines: [
      { text: "Orders ship within 2 working days.", cite: "b" },
      { text: "Delivery takes 3 to 5 days.", cite: "c" },
      { text: "Returns or exchanges within 7 days, with tags on." },
    ],
  },
  {
    title: "Opening hours",
    lines: [{ text: "Monday to Saturday, 10 AM to 7 PM." }, { text: "Sunday, 12 PM to 5 PM." }],
  },
];

/** The shop's name in the scenes (from the old illustrations). */
export const SHOP = "Indigo Lane";

/** The creator whose Reel the comment-to-DM scene plays. */
export const CREATOR = { handle: "mia.makes", post: "My studio tour, and everything I use. Comment the keyword for the full gear list." };

/** The comments that arrive under the Reel; `{K}` is the keyword, `{k}` the keyword in lower case. */
export const COMMENT_STREAM: { user: string; avatar: number; text: string; match?: boolean; spam?: boolean; name?: string }[] = [
  { user: "ritu.draws", avatar: 2, text: "This is so helpful" },
  { user: "sam.films", avatar: 4, text: "{K}", match: true, name: "Sam" },
  { user: "neha.d", avatar: 3, text: "Where is the light from?" },
  { user: "k.promo", avatar: 6, text: "Follow my page for free followers", spam: true },
  { user: "aman.k", avatar: 1, text: "{k} please", match: true, name: "Aman" },
  { user: "lena.m", avatar: 5, text: "Saving this for later" },
  { user: "divya_r", avatar: 2, text: "{K}", match: true, name: "Divya" },
  { user: "omar.v", avatar: 3, text: "Love the new setup" },
];

/** The keyword the scene starts with: the site's own example. */
export const DEFAULT_KEYWORD = "LINK";

/** The DM the automation sends, from the editor's preview (tap first, then the link). */
export const DM_SCRIPT = {
  opener: "Tap below and we'll send you the link.",
  button: "Send me the link",
  link: "Here's the full gear list.",
  url: "mia.example/gear",
  followNote: "Only to people who don't follow you yet",
  follow: "Follow along for more like this.",
};

export type ModeKey = "off" | "suggest" | "auto";

/** The four messages in the mode table, and what each mode does with them. */
export const MODE_MESSAGES: { text: string; from: string; avatar: number; label: string }[] = [
  { text: "Is the linen shirt in M?", from: "Instagram DM · Maya R.", avatar: 2, label: "Product question" },
  { text: "What time do you open on Sunday?", from: "WhatsApp · Nina", avatar: 3, label: "Opening hours" },
  { text: "Do you take bulk orders?", from: "Website chat · Visitor", avatar: 1, label: "Not in your knowledge" },
  { text: "My order arrived damaged", from: "WhatsApp · Leo M.", avatar: 4, label: "Upset customer" },
];

export const MODES: Record<ModeKey, { label: string; description: string; outcomes: [Tone, string, string][] }> = {
  off: {
    label: "Off",
    description: "No drafts. Messages still arrive tagged with intent, sentiment and a lead score, and you reply yourself.",
    outcomes: [
      ["plain", "You reply", "Tagged: product question"],
      ["plain", "You reply", "Tagged: opening hours"],
      ["plain", "You reply", "Tagged: not in your knowledge"],
      ["need", "Needs you", "Upset, so it comes to you first"],
    ],
  },
  suggest: {
    label: "Suggest",
    description: "On Free, the AI suggests replies and you send them.",
    outcomes: [
      ["draft", "AI draft", "From your price list"],
      ["draft", "AI draft", "From your opening hours"],
      ["need", "Needs you", "Knowledge gap recorded"],
      ["need", "Needs you", "Upset, so it comes to you first"],
    ],
  },
  auto: {
    label: "Auto",
    description:
      "With Auto mode (Pro), the AI replies by itself when it's confident, using your knowledge base. Anything it isn't sure about goes to Needs you.",
    outcomes: [
      ["ok", "Sent by the AI", "Yes, S to XL, $39"],
      ["ok", "Sent by the AI", "Sunday, 12 PM to 5 PM"],
      ["need", "Needs you", "Knowledge gap recorded"],
      ["need", "Needs you", "Upset, so it comes to you first"],
    ],
  },
};

/** The closing scene's inbox rows: a still inbox (C-157: no loop). */
export const MINI_ROWS: { source: SourceKey; name: string; text: string; tag: string; tone: Tone }[] = [
  { source: "web", name: "Visitor", text: "Do you take bulk orders?", tag: "Needs you", tone: "need" },
  { source: "dm", name: "Maya R.", text: "Is the linen shirt in M?", tag: "AI draft", tone: "draft" },
  { source: "whatsapp", name: "Nina", text: "What time do you open on Sunday?", tag: "AI draft", tone: "draft" },
  { source: "comment", name: "ana.wears", text: "LINK", tag: "Sent by DM", tone: "ok" },
];
