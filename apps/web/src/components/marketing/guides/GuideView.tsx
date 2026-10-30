import { ArrowLeft, ArrowRight, CalendarCheck, ChevronDown, Clock, MessageCircleQuestionMark, MessageSquareReply, Tag, Workflow } from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";
import type { CSSProperties } from "react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { TocNav, type TocItem } from "@/components/site/TocNav";
import { TocSpy } from "@/components/site/TocSpy";
import { GUIDES, GUIDES_PATH, guideDate, guidePath, sectionId, type Guide, type GuideTag } from "@/lib/marketing/guides";
import { articleJsonLd, breadcrumbTrailJsonLd } from "@/lib/marketing/seo";
import { SIGN_UP_PATH, SITE_NAME, appUrl } from "@/lib/marketing/site";

import { FinalCta } from "../FinalCta";
import { JsonLd } from "../JsonLd";
import { Ico } from "../landing/Ico";
import { CtaLink, SECTION_EYEBROW } from "../primitives";
import { SHOTS } from "../shots";

/** The id of a guide's questions section, in the table of contents too. */
const FAQ_ID = "common-questions";

/** A guide's topics as small labels (not links: there are no topic pages). */
export function GuideTags({ tags, className }: { tags: readonly GuideTag[]; className?: string }) {
  return (
    <ul aria-label="Topics" className={className ? `g-tags ${className}` : "g-tags"}>
      {tags.map((tag) => (
        <li key={tag}>{tag}</li>
      ))}
    </ul>
  );
}

/** "By Amplychat team · 28 October 2026 · 6 min read", with machine-readable dates. */
export function GuideByline({ guide }: { guide: Guide }) {
  const updated = guide.updated !== guide.published;
  return (
    <p className="g-byline">
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
 * A guide's icon (C-159): the channel's own glyph in its colour (the site's motif), or the topic's
 * icon when the guide is about automations or AI replies on that channel (iris for AI replies, an AI
 * moment).
 */
export function GuideMark({ guide }: { guide: Guide }) {
  if (guide.tags.includes("Automations")) return <Ico icon={Workflow} className="ico-mark" style={{ "--c": "var(--cm)" } as CSSProperties} />;
  if (guide.tags.includes("AI replies")) return <Ico icon={MessageSquareReply} className="ico-ai" />;
  const platform = guide.tags.includes("WhatsApp") ? "whatsapp" : "instagram";
  return (
    <Ico className="ico-mark" style={{ "--c": platform === "whatsapp" ? "var(--wa)" : "var(--ig)" } as CSSProperties}>
      <PlatformGlyph platform={platform} />
    </Ico>
  );
}

/**
 * A guide as a card (the index and "Keep reading"): its icon, topics, title (the card's one link),
 * excerpt and reading time. `featured` adds the guide's screenshot beside the text on a wide screen.
 */
export function GuideCard({ guide, featured = false, headingLevel = 3 }: { guide: Guide; featured?: boolean; headingLevel?: 2 | 3 }) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const shot = featured && guide.hero ? SHOTS[guide.hero] : null;
  return (
    <article className={featured ? "g-card g-feat" : "g-card"}>
      <div className="g-card-b">
        <div className="g-card-top">
          <GuideMark guide={guide} />
          <GuideTags tags={guide.tags} />
        </div>
        <Heading className="g-card-t">
          {/* The whole card is the link's target; the title is its name. */}
          <Link href={guidePath(guide.slug) as Route}>{guide.h1}</Link>
        </Heading>
        <p className="g-card-p">{guide.description}</p>
        <p className="g-card-m">
          <span>
            <Clock size={14} strokeWidth={1.75} aria-hidden focusable="false" /> {guide.readingMinutes} min read
          </span>
          <span aria-hidden className="g-card-go">
            <ArrowRight size={16} strokeWidth={1.75} aria-hidden focusable="false" />
          </span>
        </p>
      </div>
      {shot ? (
        <div className="g-feat-shot" aria-hidden>
          {/* Eager: on a wide screen the featured card is in the first view. */}
          <Image src={shot.src} width={shot.width} height={shot.height} alt="" sizes="18rem" loading="eager" />
        </div>
      ) : null}
    </article>
  );
}

/**
 * One guide (C-153, premium in C-159): a page head (back link, eyebrow, h1, the description as the
 * lede, byline and topics); then, from 1060 px, the article at a reading measure beside a sticky
 * column with the contents (the current section marked by TocSpy), the guide's facts and a quiet
 * Start free card. A reading-progress bar runs along the top (a CSS scroll timeline; TocSpy steps it
 * by section where the browser has none). After the article: its questions as cards, the other
 * guides and pages to read next, and the landing's night closing band. Structured data: an Article
 * (with a FAQPage when the guide has questions) and a Home, Guides, guide breadcrumb.
 */
export function GuideView({ guide }: { guide: Guide }) {
  const path = guidePath(guide.slug);
  const shot = guide.hero ? SHOTS[guide.hero] : null;
  const { Body } = guide;
  const toc: TocItem[] = [
    ...guide.sections.map((label) => ({ id: sectionId(label), label })),
    ...(guide.faq?.length ? [{ id: FAQ_ID, label: "Common questions" }] : []),
  ];
  const others = GUIDES.filter((other) => other.slug !== guide.slug);
  // The other guides show as cards; the related pages that aren't one of them follow as links.
  const also = guide.related.filter((link) => !others.some((other) => guidePath(other.slug) === link.href));
  const updated = guide.updated !== guide.published;
  return (
    <main id="main" tabIndex={-1} className="guide flex-1 outline-none">
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
      <article aria-labelledby="guide-title" className="g-article">
        <div className="g-progress" data-toc-progress="" aria-hidden />
        <header className="wrap g-head">
          <Link href={GUIDES_PATH as Route} className="g-back">
            <ArrowLeft size={16} strokeWidth={1.75} aria-hidden focusable="false" /> All guides
          </Link>
          <p className={SECTION_EYEBROW}>Guide</p>
          <h1 id="guide-title" className="h-page g-h1">
            {guide.h1}
          </h1>
          <p className="lede g-lede">{guide.description}</p>
          <div className="g-meta">
            <GuideMark guide={guide} />
            <GuideByline guide={guide} />
            <GuideTags tags={guide.tags} />
          </div>
        </header>

        <div className="wrap g-grid">
          <div className="g-main">
            <details className="g-toc-m">
              <summary>
                In this guide <ChevronDown size={16} strokeWidth={1.75} aria-hidden focusable="false" />
              </summary>
              <TocNav items={toc} label="In this guide" />
            </details>

            {shot ? (
              <figure className="g-shot">
                <div className="g-shot-f">
                  <Image
                    src={shot.src}
                    width={shot.width}
                    height={shot.height}
                    alt={shot.alt}
                    sizes="(min-width: 640px) 20rem, 16rem"
                    // Near the top of the page: loaded at once, not when scrolled to. Its box is sized by
                    // width and height, so nothing moves when it arrives.
                    loading="eager"
                  />
                </div>
                <figcaption>The {SITE_NAME} app with example data. The shop, people and messages are made up.</figcaption>
              </figure>
            ) : null}

            <div data-guide-body="" className="gprose">
              <Body />
            </div>

            {guide.faq?.length ? (
              <section aria-labelledby={FAQ_ID} className="g-faq">
                <h2 id={FAQ_ID} className="g-faq-h">
                  Common questions
                </h2>
                <dl className="g-qas">
                  {guide.faq.map((item) => (
                    <div key={item.question} className="g-qa">
                      <dt>
                        <Ico icon={MessageCircleQuestionMark} />
                        <span>{item.question}</span>
                      </dt>
                      <dd>{item.answer}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ) : null}
          </div>

          <aside className="g-side" aria-label="About this guide">
            <div className="g-side-in">
              <TocNav items={toc} className="toc-side" />
              <dl className="g-facts">
                <div>
                  <dt>
                    <Clock size={16} strokeWidth={1.75} aria-hidden focusable="false" /> Reading time
                  </dt>
                  <dd>{guide.readingMinutes} min</dd>
                </div>
                <div>
                  <dt>
                    <CalendarCheck size={16} strokeWidth={1.75} aria-hidden focusable="false" /> {updated ? "Updated" : "Published"}
                  </dt>
                  <dd>
                    <time dateTime={guide.updated}>{guideDate(guide.updated)}</time>
                  </dd>
                </div>
                <div>
                  <dt>
                    <Tag size={16} strokeWidth={1.75} aria-hidden focusable="false" /> Topics
                  </dt>
                  <dd>{guide.tags.join(", ")}</dd>
                </div>
              </dl>
              <div className="g-try">
                <p className="g-try-t">Try it on your own messages</p>
                <p className="g-try-p">The Free plan needs no card.</p>
                <CtaLink href={appUrl(SIGN_UP_PATH)} prefetch={false} className="g-try-btn">
                  Start free <ArrowRight className="size-4" aria-hidden />
                </CtaLink>
              </div>
            </div>
          </aside>
        </div>
      </article>
      <TocSpy />

      <section aria-labelledby="guide-next-title" className="g-next">
        <div className="wrap">
          <h2 id="guide-next-title" className="h-sec">
            Keep reading
          </h2>
          <ul className="g-cards g-cards-next">
            {others.map((other) => (
              <li key={other.slug}>
                <GuideCard guide={other} />
              </li>
            ))}
          </ul>
          <ul className="g-also" aria-label="Related pages">
            {also.map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} lang={link.lang} className="btn btn-line">
                  {link.label} <ArrowRight className="size-4" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <FinalCta />
    </main>
  );
}
