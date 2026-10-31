import { Rss } from "lucide-react";

import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { GuideCard } from "@/components/marketing/guides/GuideView";
import { SECTION_EYEBROW } from "@/components/marketing/primitives";
import { GUIDES, GUIDES_FEED_PATH, GUIDES_PATH } from "@/lib/marketing/guides";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";

export const metadata = pageMetadata({
  title: "Guides for Instagram and WhatsApp sellers",
  description:
    "Practical guides for businesses and creators on Instagram and WhatsApp: DM auto-replies, comment-to-DM automations and the WhatsApp Business API.",
  path: GUIDES_PATH,
  feeds: { [`${SITE_NAME} guides`]: GUIDES_FEED_PATH },
});

/**
 * The guides index (C-153, premium in C-159): a split head (the title, the lede and the feed beside
 * it), the newest guide as a wide featured card with its screenshot, the rest as a grid of cards, and
 * the landing's night closing band. Static.
 */
export default function GuidesPage() {
  const [featured, ...rest] = GUIDES;
  return (
    <main id="main" tabIndex={-1} className="guides flex-1 outline-none">
      <BreadcrumbJsonLd name="Guides" path={GUIDES_PATH} />
      <section className="page-head gi-head">
        <div className="wrap split-head">
          <div>
            <p className={SECTION_EYEBROW}>Guides</p>
            <h1 className="h-page">Sell better in the DMs</h1>
          </div>
          <div>
            <p className="lede">
              Practical guides for businesses and creators on Instagram and WhatsApp: answering faster without sounding like a
              bot, turning comments into conversations, and the rules Meta sets for all of it.
            </p>
            <p className="gi-feed">
              <a href={GUIDES_FEED_PATH} className="tlink">
                <Rss size={16} strokeWidth={1.75} aria-hidden focusable="false" /> RSS feed
              </a>
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="guides-list-title" className="gi-list">
        <div className="wrap">
          <h2 id="guides-list-title" className="sr-only">
            All guides
          </h2>
          {featured ? <GuideCard guide={featured} featured /> : null}
          <ul className="g-cards">
            {rest.map((guide) => (
              <li key={guide.slug}>
                <GuideCard guide={guide} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <FinalCta />
    </main>
  );
}
