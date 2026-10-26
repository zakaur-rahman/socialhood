import { SUPPORT_EMAIL } from "@/lib/copy";

import { GTM_PAGES } from "./gtm-pages";
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
    `${SITE_NAME} is a web app for businesses that sell on Instagram and WhatsApp. It uses Meta's official APIs. There is a Free plan; prices for paid plans are on the pricing page. Questions: ${SUPPORT_EMAIL}.`,
    "",
    "## Product",
    "",
    link("Home", "/", "what the product does, how it works, plans and common questions"),
    link("Pricing", "/pricing", "plans and every limit side by side"),
    ...GTM_PAGES.filter((page) => page.path !== "/pricing").map((page) => link(page.name, page.path, page.description)),
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
