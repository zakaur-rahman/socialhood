import { Rss } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { GuideByline, GuideTags } from "@/components/marketing/guides/GuideView";
import { Container, MARKETING_CARD, MARKETING_CARD_HOVER, SECTION_EYEBROW } from "@/components/marketing/primitives";
import { GUIDES, GUIDES_FEED_PATH, GUIDES_PATH, guidePath } from "@/lib/marketing/guides";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

export const metadata = pageMetadata({
  title: "Guides for Instagram and WhatsApp sellers",
  description:
    "Practical guides for businesses and creators on Instagram and WhatsApp: DM auto-replies, comment-to-DM automations and the WhatsApp Business API.",
  path: GUIDES_PATH,
  feeds: { [`${SITE_NAME} guides`]: GUIDES_FEED_PATH },
});

/** The guides index (C-153): every guide, newest first, with its topics. Static. */
export default function GuidesPage() {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <BreadcrumbJsonLd name="Guides" path={GUIDES_PATH} />
      <section className="page-head">
        <Container className="max-w-3xl">
          <p className={SECTION_EYEBROW}>Guides</p>
          <h1 className={"h-page"}>Sell better in the DMs</h1>
          <p className="mt-5 text-lg leading-relaxed text-pretty text-fg-secondary">
            Practical guides for businesses and creators on Instagram and WhatsApp: answering faster without sounding like a
            bot, turning comments into conversations, and the rules Meta sets for all of it.
          </p>
          <p className="mt-4 text-sm">
            <a
              href={GUIDES_FEED_PATH}
              className="inline-flex min-h-10 items-center gap-1.5 font-medium text-brand-fg underline-offset-4 hover:underline"
            >
              <Rss className="size-4" aria-hidden /> RSS feed
            </a>
          </p>
        </Container>
      </section>

      <section aria-labelledby="guides-list-title" className="band">
        <Container className="max-w-3xl">
          <h2 id="guides-list-title" className="sr-only">
            All guides
          </h2>
          <ul className="grid gap-4">
            {GUIDES.map((guide) => (
              <li key={guide.slug}>
                <article className={cn(MARKETING_CARD, MARKETING_CARD_HOVER, "relative flex flex-col gap-3 p-5 sm:p-6")}>
                  <GuideTags tags={guide.tags} />
                  <h3 className="text-xl font-semibold tracking-tight text-balance">
                    {/* The whole card is the link's target; the title is its name. */}
                    <Link
                      href={guidePath(guide.slug) as Route}
                      className="rounded-sm after:absolute after:inset-0 after:rounded-2xl hover:text-brand-fg"
                    >
                      {guide.h1}
                    </Link>
                  </h3>
                  <p className="text-base leading-relaxed text-fg-secondary">{guide.description}</p>
                  <GuideByline guide={guide} />
                </article>
              </li>
            ))}
          </ul>
        </Container>
      </section>
    </main>
  );
}
