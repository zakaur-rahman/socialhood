import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";

import { PRICING_PATH, STATUS_LABEL, type Cell, type GtmPage } from "@/lib/marketing/gtm-pages";
import { SIGN_UP_PATH } from "@/lib/marketing/site";
import { cn } from "@/lib/utils";
import { MARKETING_HEADING } from "@/styles/tokens";

import { Container, CtaLink, SECTION_EYEBROW } from "./primitives";
import { SHOTS } from "./shots";

const LINK = "font-medium text-brand-fg underline-offset-4 hover:underline";

function CellView({ cell }: { cell: Cell }) {
  return (
    <>
      <span className={cn("block text-sm font-medium", cell.status === "yes" ? "text-fg" : "text-fg-secondary")}>
        {STATUS_LABEL[cell.status]}
      </span>
      {cell.text ? <span className="mt-1 block text-sm leading-relaxed text-fg-secondary">{cell.text}</span> : null}
    </>
  );
}

function Compare({ page }: { page: GtmPage }) {
  if (!page.compare) return null;
  const { competitor, caption, rows } = page.compare;
  return (
    <section aria-labelledby="compare-title" className="border-t border-line-subtle py-14 sm:py-16">
      <Container>
        <h2 id="compare-title" className="text-2xl font-semibold tracking-tight">
          Side by side
        </h2>
        {/* The table scrolls inside this box on a phone; the page itself never scrolls sideways. */}
        <div
          role="region"
          aria-label={caption}
          tabIndex={0}
          className="mt-6 overflow-x-auto rounded-2xl border border-line bg-panel-glass focus-visible:outline-offset-2"
        >
          <table className="w-full min-w-[40rem] border-collapse text-left">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr className="border-b border-line text-sm">
                <th scope="col" className="w-1/4 px-4 py-3 font-semibold">
                  Feature
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  Social Hood
                </th>
                <th scope="col" className="px-4 py-3 font-semibold">
                  {competitor}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.feature} className="border-b border-line-subtle align-top last:border-b-0">
                  <th scope="row" className="px-4 py-4 text-sm font-medium">
                    {row.feature}
                  </th>
                  <td className="px-4 py-4">
                    <CellView cell={row.ours} />
                  </td>
                  <td className="px-4 py-4">
                    <CellView cell={row.theirs} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Container>
    </section>
  );
}

/**
 * A go-to-market page (GR-37): the hero with one h1, the content blocks as h2 sections, a
 * side-by-side table on the comparison pages, how it was checked (what is not done, the sources
 * and the date each was read), related pages and a sign-up. The content is lib/marketing/gtm-pages.ts.
 */
export function GtmPageView({ page }: { page: GtmPage }) {
  const shot = page.shot ? SHOTS[page.shot] : null;
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <section className="py-16 sm:py-20">
        <Container className="max-w-3xl">
          <p className={SECTION_EYEBROW}>{page.eyebrow}</p>
          <h1 className={cn(MARKETING_HEADING, "mt-3 text-balance sm:text-5xl")}>{page.h1}</h1>
          <p className="mt-5 text-lg leading-relaxed text-pretty text-fg-secondary">{page.intro}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <CtaLink href={SIGN_UP_PATH} prefetch={false} className="w-full px-6 sm:w-auto">
              Start free <ArrowRight className="size-4" aria-hidden />
            </CtaLink>
            <CtaLink href={PRICING_PATH} variant="secondary" className="w-full px-6 sm:w-auto">
              See plans and limits
            </CtaLink>
          </div>
        </Container>
      </section>

      {shot ? (
        <Container className="max-w-4xl pb-14">
          <figure>
            <Image
              src={shot.src}
              width={shot.width}
              height={shot.height}
              alt={shot.alt}
              sizes="(min-width: 960px) 896px, calc(100vw - 2rem)"
              className="h-auto w-full max-w-md rounded-2xl border border-line sm:max-w-full"
            />
            <figcaption className="mt-3 text-xs text-fg-secondary">
              The Social Hood app with example data. The shop, people and messages are made up.
            </figcaption>
          </figure>
        </Container>
      ) : null}

      {page.blocks.map((block) => (
        <section key={block.id} id={block.id} aria-labelledby={`${block.id}-title`} className="scroll-mt-24 border-t border-line-subtle py-14 sm:py-16">
          <Container>
            <h2 id={`${block.id}-title`} className="text-2xl font-semibold tracking-tight">
              {block.title}
            </h2>
            {block.intro ? <p className="mt-3 max-w-2xl text-base text-fg-secondary">{block.intro}</p> : null}
            <ul className="mt-8 grid gap-4 sm:grid-cols-2">
              {block.items.map((item) => (
                <li key={item.title} className="rounded-2xl border border-line bg-panel p-5">
                  <h3 className="text-base font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-fg-secondary">{item.body}</p>
                </li>
              ))}
            </ul>
          </Container>
        </section>
      ))}

      <Compare page={page} />

      <section aria-labelledby="checked-title" className="border-t border-line-subtle py-14 sm:py-16">
        <Container className="max-w-3xl">
          <h2 id="checked-title" className="text-2xl font-semibold tracking-tight">
            What to know before you decide
          </h2>
          <ul className="mt-6 list-disc space-y-3 pl-5 text-sm leading-relaxed text-fg-secondary">
            {page.honesty.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {page.sources.length > 0 ? (
            <>
              <h3 className="mt-8 text-base font-semibold">Sources</h3>
              <ul className="mt-3 space-y-2 text-sm text-fg-secondary" aria-label="Sources">
                {page.sources.map((source) => (
                  <li key={source.url}>
                    <a href={source.url} rel="noopener noreferrer" className={LINK}>
                      {source.label}
                    </a>{" "}
                    <span>(read {source.checked})</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </Container>
      </section>

      <section aria-labelledby="related-title" className="border-t border-line-subtle py-14 sm:py-16">
        <Container className="max-w-3xl">
          <h2 id="related-title" className="text-2xl font-semibold tracking-tight">
            Keep reading
          </h2>
          <ul className="mt-5 grid gap-1 text-sm">
            {page.related.map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} className={cn(LINK, "inline-flex min-h-10 items-center")}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-8">
            <CtaLink href={SIGN_UP_PATH} prefetch={false} className="w-full px-6 sm:w-auto">
              Start free
            </CtaLink>
          </div>
        </Container>
      </section>
    </main>
  );
}
