import { COMMENT_TO_DM } from "./comment-to-dm-automations";
import { INSTAGRAM_DM_AUTO_REPLIES } from "./instagram-dm-auto-replies";
import { REPLYING_IN_HINGLISH } from "./replying-in-hinglish";
import type { Guide } from "./types";
import { WHATSAPP_API_VS_APP } from "./whatsapp-business-api-vs-app";

export * from "./types";

/**
 * Every guide, newest first (C-153); ties keep the order written here. The index, the article
 * routes, the sitemap, the RSS feed and llms.txt all read this list.
 */
export const GUIDES: readonly Guide[] = [INSTAGRAM_DM_AUTO_REPLIES, WHATSAPP_API_VS_APP, COMMENT_TO_DM, REPLYING_IN_HINGLISH]
  .map((guide, order) => ({ guide, order }))
  .sort((a, b) => b.guide.published.localeCompare(a.guide.published) || a.order - b.order)
  .map(({ guide }) => guide);

export function findGuide(slug: string): Guide | undefined {
  return GUIDES.find((guide) => guide.slug === slug);
}

/** The newest `updated` date of any guide: the index page's and the feed's last change. */
export function guidesUpdated(guides: readonly Guide[] = GUIDES): string {
  return guides.reduce((latest, guide) => (guide.updated > latest ? guide.updated : latest), "");
}

/** "28 October 2026", as the legal pages write dates. */
export function guideDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}
