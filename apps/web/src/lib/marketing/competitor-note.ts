import { SUPPORT_EMAIL } from "@/lib/copy";
import { legalDate } from "@/lib/legal";

import type { GtmPage } from "./gtm-pages";
import { SITE_NAME } from "./site";

/** The newest `checked` date of a page's sources, as an ISO date; null when it has none. */
export function latestChecked(page: Pick<GtmPage, "sources">): string | null {
  return page.sources.reduce<string | null>((latest, source) => (latest === null || source.checked > latest ? source.checked : latest), null);
}

/**
 * The trademark and no-affiliation note on a page about a competitor (C-155): the competitor's
 * name is its owner's trademark, we aren't affiliated with or endorsed by it, the date we last
 * checked its details, and where to tell us if they've changed. The email is returned on its own
 * so the page can link it. Null for a page that isn't about a competitor.
 */
export function competitorNote(page: GtmPage): { text: string; email: string } | null {
  if (!page.competitor) return null;
  const checked = legalDate(latestChecked(page));
  const name = page.competitor;
  return {
    text: [
      `${name} is a trademark of its owner.`,
      `${SITE_NAME} isn't affiliated with or endorsed by ${name}.`,
      checked ? `Details checked on ${checked}.` : null,
      "If something has changed, tell us at",
    ]
      .filter(Boolean)
      .join(" "),
    email: SUPPORT_EMAIL,
  };
}
