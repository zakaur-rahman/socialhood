import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { FinalCta } from "@/components/marketing/FinalCta";
import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { Ico } from "@/components/marketing/landing/Ico";
import { SOURCES } from "@/components/marketing/landing/data";
import { HOW_WE_COMPARE_ICONS } from "@/components/marketing/page-icons";
import { SECTION_EYEBROW } from "@/components/marketing/primitives";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { legalDate } from "@/lib/legal";
import { latestChecked } from "@/lib/marketing/competitor-note";
import { COMPARE_GROUPS, COMPARE_PATH } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";

export const metadata = pageMetadata({
  title: `How ${SITE_NAME} compares`,
  description:
    "Amplychat side by side with Instagram DM tools and WhatsApp platforms, from each vendor's own dated pages, with our side checked against our code.",
  path: COMPARE_PATH,
});

const HOW = [
  "Each competitor's column comes from its own pricing, product and help pages, listed as sources on the page.",
  "Every source shows the date we read it. Prices and plans change, so check the vendor's site before you decide.",
  "Our column is checked against our own code. Anything that waits on Meta, Shopify or a legal review says so.",
  "“Not found” means we didn't see it on the pages we read, not that the product lacks it.",
];

/** Each group's mark: the channel it is about, in its colour (the site's one motif). */
const GROUP_MARK = {
  "instagram-dm-tools": { platform: "instagram", colour: SOURCES.dm.colour },
  "whatsapp-platforms": { platform: "whatsapp", colour: SOURCES.whatsapp.colour },
} as const;

/**
 * The comparisons hub (C-156; C-159 look): how we compare as four icon cards, then every comparison
 * and Switch from Manychat as linked cards in two groups (each group marked with its channel's
 * glyph), each with the date its sources were read, the trademark note as a footnote card and the
 * closing band. Static, from lib/marketing/gtm-pages.ts.
 */
export default function ComparePage() {
  return (
    <main id="main" tabIndex={-1} className="pp flex-1 outline-none">
      <BreadcrumbJsonLd name="Compare" path={COMPARE_PATH} />
      <section className="page-head pp-head">
        <div className="wrap">
          <p className={SECTION_EYEBROW}>Compare</p>
          <h1 className="h-page">How {SITE_NAME} compares</h1>
          <p className="lede">
            {SITE_NAME} puts Instagram, WhatsApp and website chat in one inbox, with AI that answers from your own knowledge and
            hands the rest to a person, comment analysis and publishing. Here is how it sits next to other tools, including where
            they are stronger.
          </p>
        </div>
      </section>

      <section aria-labelledby="how-title" className="band">
        <div className="wrap">
          <h2 id="how-title" className="h-sec">
            How we compare
          </h2>
          <ul className="gcards is-4 after-head">
            {HOW.map((line, index) => (
              <li key={line} className="gcard is-plain">
                <Ico icon={HOW_WE_COMPARE_ICONS[index]} />
                <p>{line}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {COMPARE_GROUPS.map((group) => {
        const mark = GROUP_MARK[group.id as keyof typeof GROUP_MARK];
        return (
          <section key={group.id} id={group.id} aria-labelledby={`${group.id}-title`} className="band scroll-mt-24">
            <div className="wrap">
              <div className="split-head">
                <h2 id={`${group.id}-title`} className="h-sec pp-group-h">
                  {mark ? (
                    <Ico className="ico-mark" style={{ "--c": mark.colour } as CSSProperties}>
                      <PlatformGlyph platform={mark.platform} />
                    </Ico>
                  ) : null}
                  {group.title}
                </h2>
                <p className="lede">{group.intro}</p>
              </div>
              <ul className="hub after-head">
                {group.pages.map((page) => {
                  const checked = legalDate(latestChecked(page));
                  return (
                    <li key={page.path}>
                      <article className="hcard">
                        <h3>
                          {/* The whole card is the link's target; the title is its name. */}
                          <Link href={page.path as Route} className="hcard-link">
                            {page.name}
                          </Link>
                          <ArrowRight className="hcard-arrow size-4" aria-hidden />
                        </h3>
                        <p>{page.description}</p>
                        {checked ? <p className="hcard-date">Checked on {checked}</p> : null}
                      </article>
                    </li>
                  );
                })}
              </ul>
            </div>
          </section>
        );
      })}

      <section aria-labelledby="note-title" className="band">
        <div className="wrap">
          <div className="fnote is-wide">
            <h2 id="note-title" className="h-sec">
              Something out of date?
            </h2>
            <p className="fnote-tm">
              Product names on these pages are trademarks of their owners. {SITE_NAME} isn&apos;t affiliated with or endorsed by any
              of them. If a detail has changed, tell us at{" "}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="tlink">
                {SUPPORT_EMAIL}
              </a>{" "}
              and we&apos;ll correct it.
            </p>
          </div>
        </div>
      </section>
      <FinalCta />
    </main>
  );
}
