import { SUPPORT_EMAIL } from "@/lib/copy";

import { COMPARE_PATH, GTM_PAGES } from "./gtm-pages";
import { GUIDES, GUIDES_PATH, guidePath } from "./guides";
import { LEGAL_LINKS, SITE_DESCRIPTION, SITE_NAME, absoluteUrl, siteUrl } from "./site";

/**
 * /llms.txt (llmstxt.org): a plain description of the product and links to the public pages, for
 * AI assistants that read the site (C-142). Markdown, from the same data the pages render.
 */
export function llmsText(origin: string = siteUrl()): string {
  const link = (label: string, path: string, note?: string) => `- [${label}](${absoluteUrl(path, origin)})${note ? `: ${note}` : ""}`;
  return [
    `# ${SITE_NAME}`,
    "",
    `> ${SITE_DESCRIPTION}`,
    "",
    `${SITE_NAME} is a web app for businesses and creators on Instagram and WhatsApp. It uses Meta's official APIs. There is a Free plan; prices for paid plans are on the pricing page. Questions: ${SUPPORT_EMAIL}.`,
    "",
    `For a plain fact sheet about ${SITE_NAME} (what it is, who it's for, channels and their status, plans, honest limits and claims to avoid), read the AI info page first.`,
    "",
    "## Start here",
    "",
    link("AI info", "/ai-info", "a fact sheet for AI assistants: what is true today, and what not to claim"),
    link("Safety", "/safety", "Meta's limits and how sends are queued, official login, and what we never do"),
    link("What's new", "/changelog", "dated list of shipped features"),
    "",
    "## Product",
    "",
    link("Home", "/", "what the product does, how it works, plans and common questions"),
    link("Pricing", "/pricing", "plans and every limit side by side"),
    link("For creators", "/for-creators", "comment-to-DM, scheduling, AI replies from your notes, comment analysis"),
    link("For businesses", "/for-businesses", "one inbox for Instagram, WhatsApp and web chat, AI from your knowledge, leads"),
    link("All comparisons", COMPARE_PATH, "how Amplychat compares with other tools"),
    ...GTM_PAGES.filter((page) => page.path !== "/pricing").map((page) => link(page.name, page.path, page.description)),
    "",
    "## Guides",
    "",
    link("All guides", GUIDES_PATH, "practical guides for businesses and creators on Instagram and WhatsApp"),
    ...GUIDES.map((guide) => link(guide.h1, guidePath(guide.slug), guide.description)),
    "",
    "## Developers",
    "",
    link("Public API", "/developers/api", "authentication, scopes and every operation of the public REST API"),
    "",
    "## Legal",
    "",
    ...LEGAL_LINKS.filter((item) => (item.href as string) !== "/security").map((item) => link(item.label, item.href)),
    link("Security", "/security", "how we protect data and how to report a vulnerability"),
    "",
  ].join("\n");
}
