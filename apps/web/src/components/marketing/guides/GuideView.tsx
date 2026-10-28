import { ArrowLeft, ArrowRight } from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";

import { GUIDES_PATH, guideDate, guidePath, type Guide, type GuideTag } from "@/lib/marketing/guides";
import { articleJsonLd, breadcrumbTrailJsonLd } from "@/lib/marketing/seo";
import { PRICING_PATH } from "@/lib/marketing/gtm-pages";
import { SIGN_UP_PATH, SITE_NAME, appUrl } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";

import { JsonLd } from "../JsonLd";
import { Container, CtaLink, MARKETING_CARD, SECTION_EYEBROW } from "../primitives";
import { PROSE } from "../prose";
import { SHOTS } from "../shots";

const LINK = "font-medium text-brand-fg underline-offset-4 hover:underline";

/** A guide's topics as small labels (not links: there are no topic pages). */
export function GuideTags({ tags, className }: { tags: readonly GuideTag[]; className?: string }) {
  return (
    <ul aria-label="Topics" className={cn("flex flex-wrap gap-1.5", className)}>
      {tags.map((tag) => (
        <li key={tag} className="rounded-full border border-line px-2.5 py-0.5 text-xs text-fg-secondary">
          {tag}
        </li>
      ))}
    </ul>
  );
}

/** "By Amplychat team · 28 October 2026 · 6 min read", with machine-readable dates. */
export function GuideByline({ guide }: { guide: Guide }) {
  const updated = guide.updated !== guide.published;
  return (
    <p className="text-sm text-fg-secondary">
      <span>By {guide.author}</span>
      <span aria-hidden> · </span>
      <time dateTime={guide.published}>{guideDate(guide.published)}</time>
      {updated ? (
        <>
          <span aria-hidden> · </span>
          <span>
            Updated <time dateTime={guide.updated}>{guideDate(guide.updated)}</time>
          </span>
        </>
      ) : null}
      <span aria-hidden> · </span>
      <span>{guide.readingMinutes} min read</span>
    </p>
  );
}

/**
 * One guide (C-153): a link back to the index, the h1 with its byline, an optional product
 * screenshot, the body in the shared prose styles, its questions and answers, a soft call to
 * action and pages to read next. Structured data: an Article (with a FAQPage when the guide has
 * questions) and a Home, Guides, guide breadcrumb.
 */
export function GuideView({ guide }: { guide: Guide }) {
  const path = guidePath(guide.slug);
  const shot = guide.hero ? SHOTS[guide.hero] : null;
  const { Body } = guide;
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <JsonLd
        data={articleJsonLd({
          path,
          title: guide.title,
          description: guide.description,
          published: guide.published,
          updated: guide.updated,
          author: guide.author,
          tags: guide.tags,
          faq: guide.faq,
        })}
      />
      <JsonLd
        data={breadcrumbTrailJsonLd([
          { name: "Guides", path: GUIDES_PATH },
          { name: guide.title, path },
        ])}
      />
      <article aria-labelledby="guide-title">
        <Container className="max-w-3xl pt-12 sm:pt-16">
          <Link href={GUIDES_PATH as Route} className={cn(LINK, "inline-flex min-h-10 items-center gap-1.5 text-sm")}>
            <ArrowLeft className="size-4" aria-hidden /> All guides
          </Link>
          <header className="mt-4">
            <p className={SECTION_EYEBROW}>Guide</p>
            <h1 id="guide-title" className={"h-page"}>
              {guide.h1}
            </h1>
            <div className="mt-4 flex flex-col gap-3">
              <GuideByline guide={guide} />
              <GuideTags tags={guide.tags} />
            </div>
          </header>

          {shot ? (
            <figure className="mt-10">
              <Image
                src={shot.src}
                width={shot.width}
                height={shot.height}
                alt={shot.alt}
                sizes="(min-width: 640px) 20rem, 16rem"
                // Near the top of the page: loaded at once, not when scrolled to. Its box is sized by
                // width and height, so nothing moves when it arrives.
                loading="eager"
                className="h-auto w-full max-w-64 rounded-2xl border border-line sm:max-w-xs"
              />
              <figcaption className="mt-3 text-xs text-fg-secondary">
                The {SITE_NAME} app with example data. The shop, people and messages are made up.
              </figcaption>
            </figure>
          ) : null}

          <div data-guide-body="" className={cn("mt-10", PROSE, "[&_h2]:mt-12 [&_h3]:mt-8")}>
            <Body />
          </div>
        </Container>

        {guide.faq?.length ? (
          <section aria-labelledby="guide-faq-title" className="mt-14 border-t border-line-subtle py-14">
            <Container className="max-w-3xl">
              <h2 id="guide-faq-title" className="h-sec">
                Common questions
              </h2>
              <dl className="mt-6 space-y-6">
                {guide.faq.map((item) => (
                  <div key={item.question}>
                    <dt className="text-base font-semibold">{item.question}</dt>
                    <dd className="mt-2 text-base leading-relaxed text-fg-secondary">{item.answer}</dd>
                  </div>
                ))}
              </dl>
            </Container>
          </section>
        ) : null}
      </article>

      <section aria-labelledby="guide-next-title" className="border-t border-line-subtle py-14">
        <Container className="max-w-3xl">
          <div className={cn(MARKETING_CARD, "p-6 sm:p-8")}>
            <h2 id="guide-next-title" className="h-sec">
              Try it on your own messages
            </h2>
            <p className="mt-3 text-base leading-relaxed text-fg-secondary">
              {SITE_NAME} brings Instagram DMs, comments and WhatsApp into one inbox, with AI replies from your own knowledge.
              The Free plan needs no card.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="w-full px-6 sm:w-auto">
                Start free <ArrowRight className="size-4" aria-hidden />
              </CtaLink>
              <CtaLink href={PRICING_PATH} variant="secondary" className="w-full px-6 sm:w-auto">
                See plans and limits
              </CtaLink>
            </div>
          </div>
          <h2 className="mt-12 text-lg font-semibold">Keep reading</h2>
          <ul className="mt-3 grid gap-1 text-sm">
            {guide.related.map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} lang={link.lang} className={cn(LINK, "inline-flex min-h-10 items-center")}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </Container>
      </section>
    </main>
  );
}
