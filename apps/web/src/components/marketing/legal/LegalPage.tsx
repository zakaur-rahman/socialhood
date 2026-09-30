import type { ReactNode } from "react";

import { LEGAL, LEGAL_DOCUMENTS, legalDate, legalFacts, type LegalConfig, type LegalDocumentKey } from "@/lib/legal";

import { Container } from "../primitives";

export type LegalSection = { id: string; title: string; body: ReactNode };

// Prose styles for the documents (no typography plugin): headings, paragraphs, lists and links.
const PROSE = [
  "text-[15px] leading-relaxed text-fg-secondary",
  "[&_h2]:scroll-mt-24 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-fg",
  "[&_h3]:mt-6 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-fg",
  "[&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5 [&_ol]:mt-3 [&_ol]:list-decimal [&_ol]:space-y-1.5 [&_ol]:pl-5",
  "[&_li]:pl-1 [&_strong]:font-semibold [&_strong]:text-fg",
  "[&_a]:font-medium [&_a]:text-brand-fg [&_a]:underline [&_a]:underline-offset-4",
  "[&_table]:mt-4 [&_table]:w-full [&_table]:text-sm [&_th]:border-b [&_th]:border-line [&_th]:py-2 [&_th]:pr-4 [&_th]:text-left [&_th]:font-semibold [&_th]:text-fg",
  "[&_td]:border-b [&_td]:border-line-subtle [&_td]:py-2 [&_td]:pr-4 [&_td]:align-top",
].join(" ");

/** The "who we are" details that are set; nothing at all for the unset ones. */
export function LegalFacts({ config = LEGAL }: { config?: LegalConfig }) {
  const facts = legalFacts(config);
  if (!facts.length) return null;
  return (
    <dl className="mt-4 grid gap-x-6 gap-y-2 rounded-xl border border-line bg-panel p-4 text-sm sm:grid-cols-[auto_1fr]">
      {facts.map((fact) => (
        <div key={fact.label} className="contents">
          <dt className="text-fg-secondary">{fact.label}</dt>
          <dd className="text-fg">{fact.href ? <a href={fact.href}>{fact.value}</a> : fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** "Last updated 1 October 2026", and "Effective …" once the owner sets it. */
export function LegalDates({ document, config = LEGAL }: { document: LegalDocumentKey; config?: LegalConfig }) {
  const updated = legalDate(LEGAL_DOCUMENTS[document].lastUpdated);
  const effective = legalDate(config.effectiveDate);
  return (
    <p className="mt-3 text-sm text-fg-secondary">
      {updated ? <>Last updated {updated}</> : null}
      {updated && effective ? <span aria-hidden> · </span> : null}
      {effective ? <>Effective {effective}</> : null}
    </p>
  );
}

/**
 * A legal document: title, dates, a summary, contents and the numbered sections. Server-rendered
 * and static; the contents list sits beside the text on wide screens.
 */
export function LegalPage({
  document,
  summary,
  sections,
}: {
  document: LegalDocumentKey;
  summary: ReactNode;
  sections: LegalSection[];
}) {
  const { title } = LEGAL_DOCUMENTS[document];
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <Container className="py-12 sm:py-16">
        <header className="max-w-3xl">
          <p className="text-xs font-semibold tracking-[0.14em] text-brand-fg uppercase">Legal</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          <LegalDates document={document} />
          <div className="mt-6 rounded-xl border border-line bg-panel p-5 text-[15px] leading-relaxed text-fg-secondary [&_a]:text-brand-fg [&_a]:underline [&_a]:underline-offset-4 [&_p+p]:mt-3 [&_strong]:text-fg">
            {summary}
          </div>
        </header>

        <div className="mt-10 grid gap-10 lg:grid-cols-[14rem_1fr]">
          <nav aria-labelledby="contents-title" className="lg:sticky lg:top-24 lg:self-start">
            <h2 id="contents-title" className="text-xs font-semibold tracking-[0.14em] text-fg uppercase">
              Contents
            </h2>
            <ol className="mt-3 grid gap-0.5 text-sm">
              {sections.map((section, index) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="flex min-h-10 items-center gap-2 rounded-md px-2 text-fg-secondary hover:bg-raised hover:text-fg lg:min-h-8"
                  >
                    <span className="w-5 shrink-0 text-xs tabular-nums">{index + 1}.</span>
                    {section.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <div className={`max-w-3xl space-y-12 ${PROSE}`}>
            {sections.map((section, index) => (
              <section key={section.id} aria-labelledby={section.id}>
                <h2 id={section.id}>
                  {index + 1}. {section.title}
                </h2>
                {section.body}
              </section>
            ))}
          </div>
        </div>
      </Container>
    </main>
  );
}
