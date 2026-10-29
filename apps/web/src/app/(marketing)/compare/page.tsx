import type { Route } from "next";
import Link from "next/link";

import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { Container, MARKETING_CARD, MARKETING_CARD_HOVER, SECTION_EYEBROW } from "@/components/marketing/primitives";
import { SUPPORT_EMAIL } from "@/lib/copy";
import { legalDate } from "@/lib/legal";
import { latestChecked } from "@/lib/marketing/competitor-note";
import { COMPARE_GROUPS, COMPARE_PATH } from "@/lib/marketing/gtm-pages";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

export const metadata = pageMetadata({
  title: `How ${SITE_NAME} compares`,
  description:
    "Amplychat side by side with Instagram DM tools and WhatsApp platforms, from each vendor's own dated pages, with our side checked against our code.",
  path: COMPARE_PATH,
});

const LINK = "font-medium text-brand-fg underline-offset-4 hover:underline";

/**
 * The comparisons hub (C-156): how we compare, then every comparison and Switch from Manychat as
 * cards in two groups, each with the date its sources were read. Static, from lib/marketing/gtm-pages.ts.
 */
export default function ComparePage() {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <BreadcrumbJsonLd name="Compare" path={COMPARE_PATH} />
      <section className="page-head">
        <Container className="max-w-3xl">
          <p className={SECTION_EYEBROW}>Compare</p>
          <h1 className="h-page">How {SITE_NAME} compares</h1>
          <p className="mt-5 text-lg leading-relaxed text-pretty text-fg-secondary">
            {SITE_NAME} puts Instagram, WhatsApp and website chat in one inbox, with AI that answers from your own knowledge
            and hands the rest to a person, comment analysis and publishing. Here is how it sits next to other tools, including
            where they are stronger.
          </p>
        </Container>
      </section>

      <section aria-labelledby="how-title" className="band">
        <Container className="max-w-3xl">
          <h2 id="how-title" className="h-sec">
            How we compare
          </h2>
          <ul className="mt-6 list-disc space-y-3 pl-5 text-base leading-relaxed text-fg-secondary">
            <li>Each competitor&apos;s column comes from its own pricing, product and help pages, listed as sources on the page.</li>
            <li>Every source shows the date we read it. Prices and plans change, so check the vendor&apos;s site before you decide.</li>
            <li>Our column is checked against our own code. Anything that waits on Meta, Shopify or a legal review says so.</li>
            <li>&ldquo;Not found&rdquo; means we didn&apos;t see it on the pages we read, not that the product lacks it.</li>
          </ul>
        </Container>
      </section>

      {COMPARE_GROUPS.map((group) => (
        <section key={group.id} id={group.id} aria-labelledby={`${group.id}-title`} className="band scroll-mt-24">
          <Container>
            <h2 id={`${group.id}-title`} className="h-sec">
              {group.title}
            </h2>
            <p className="mt-3 max-w-2xl text-base text-fg-secondary">{group.intro}</p>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {group.pages.map((page) => {
                const checked = legalDate(latestChecked(page));
                return (
                  <li key={page.path}>
                    <article className={cn(MARKETING_CARD, MARKETING_CARD_HOVER, "relative flex h-full flex-col gap-2 p-5")}>
                      <h3 className="text-lg font-semibold tracking-tight">
                        {/* The whole card is the link's target; the title is its name. */}
                        <Link href={page.path as Route} className="rounded-sm after:absolute after:inset-0 after:rounded-2xl hover:text-brand-fg">
                          {page.name}
                        </Link>
                      </h3>
                      <p className="text-sm leading-relaxed text-fg-secondary">{page.description}</p>
                      {checked ? <p className="mt-auto pt-2 text-xs text-fg-secondary">Checked on {checked}</p> : null}
                    </article>
                  </li>
                );
              })}
            </ul>
          </Container>
        </section>
      ))}

      <section aria-labelledby="note-title" className="band">
        <Container className="max-w-3xl">
          <h2 id="note-title" className="h-sec">
            Something out of date?
          </h2>
          <p className="mt-4 text-base leading-relaxed text-fg-secondary">
            Product names on these pages are trademarks of their owners. {SITE_NAME} isn&apos;t affiliated with or endorsed by any of
            them. If a detail has changed, tell us at{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className={LINK}>
              {SUPPORT_EMAIL}
            </a>{" "}
            and we&apos;ll correct it.
          </p>
        </Container>
      </section>
    </main>
  );
}
