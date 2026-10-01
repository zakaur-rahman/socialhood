/**
 * The product screenshots in public/marketing (scripts/marketing-shots: the real app on the e2e
 * stack, sandbox data, made-up names). Sizes are the files' pixels at 2x; shots.test.ts checks
 * them against the files, so a refreshed screenshot of a different shape fails until this changes.
 */
export type Shot = { src: string; width: number; height: number; alt: string };

export const SHOTS = {
  inbox: {
    src: "/marketing/inbox.webp",
    width: 2880,
    height: 1800,
    alt: "The Social Hood inbox: Instagram conversations on the left, a customer asking whether a linen shirt is in stock, and an AI draft reply waiting to be sent, edited or dismissed.",
  },
  connect: {
    src: "/marketing/connect.webp",
    width: 1128,
    height: 772,
    alt: "A connected Instagram account in Settings, Connections, with AI replies set to Suggest and AI analysis on.",
  },
  knowledge: {
    src: "/marketing/knowledge.webp",
    width: 768,
    height: 726,
    alt: "An FAQ in the knowledge base: the question “How long does delivery take?” and the shop's answer.",
  },
  aiDraft: {
    src: "/marketing/ai-draft.webp",
    width: 1070,
    height: 1092,
    alt: "A conversation with an AI draft above the reply box, with Send, Insert and Draft again.",
  },
  automationPreview: {
    src: "/marketing/automation-preview.webp",
    width: 612,
    height: 1152,
    alt: "The automation editor's preview: a comment saying LINK, the public reply “Sent you a DM!”, a DM with a “Send me the link” button, the link after the tap, and a follow invitation sent only to people who don't follow.",
  },
} satisfies Record<string, Shot>;
