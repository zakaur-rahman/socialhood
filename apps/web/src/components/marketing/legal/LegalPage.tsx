import {
  Briefcase,
  Building2,
  CalendarDays,
  ChevronDown,
  Info,
  ListChecks,
  type LucideIcon,
  Mail,
  MapPin,
  Phone,
  Scale,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";

import { Ico } from "@/components/marketing/landing/Ico";
import { TocSpy } from "@/components/site/TocSpy";
import { LEGAL, LEGAL_DOCUMENTS, legalDate, legalFacts, type LegalConfig, type LegalDocumentKey } from "@/lib/legal";

import { SECTION_EYEBROW } from "../primitives";

export type LegalSection = { id: string; title: string; body: ReactNode };

/** Each "who we are" fact's icon (C-159); the label beside it says the same thing. */
const FACT_ICONS: Record<string, LucideIcon> = {
  "Operated by": Building2,
  "Business type": Briefcase,
  Proprietor: UserRound,
  "Registered address": MapPin,
  Location: MapPin,
  Phone,
  Email: Mail,
  "Grievance officer": Scale,
};

/**
 * The "who we are" details that are set; nothing at all for the unset ones. A callout of facts
 * (C-159): each with its icon, label and value, in as many columns as fit.
 */
export function LegalFacts({ config = LEGAL }: { config?: LegalConfig }) {
  const facts = legalFacts(config);
  if (!facts.length) return null;
  return (
    <div className="lfacts" data-legal-facts="">
      <dl>
        {facts.map((fact) => (
          <div key={fact.label} className="lfact">
            <dt>
              <Ico icon={FACT_ICONS[fact.label] ?? Info} />
              <span>{fact.label}</span>
            </dt>
            <dd>{fact.href ? <a href={fact.href}>{fact.value}</a> : fact.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** "Last updated 1 October 2026", and "Effective …" once the owner sets it. */
export function LegalDates({ document, config = LEGAL }: { document: LegalDocumentKey; config?: LegalConfig }) {
  const updated = legalDate(LEGAL_DOCUMENTS[document].lastUpdated);
  const effective = legalDate(config.effectiveDate);
  if (!updated && !effective) return null;
  return (
    <p className="legal-meta">
      <CalendarDays size={16} strokeWidth={1.75} aria-hidden focusable="false" />
      {updated ? <span>Last updated {updated}</span> : null}
      {updated && effective ? <span aria-hidden> · </span> : null}
      {effective ? <span>Effective {effective}</span> : null}
    </p>
  );
}

/** The contents: a list of the numbered sections, open beside the text on a wide screen and a
 *  disclosure above it on a narrower one. TocSpy marks the section being read. */
export function LegalContents({ sections }: { sections: readonly { id: string; title: string }[] }) {
  return (
    <nav aria-labelledby="contents-title" className="toc" data-toc="">
      <details className="toc-d">
        <summary>
          <span id="contents-title" className="toc-t">
            Contents
          </span>
          <ChevronDown size={18} strokeWidth={1.75} aria-hidden focusable="false" className="toc-chev" />
        </summary>
        <ol>
          {sections.map((section, index) => (
            <li key={section.id}>
              <a href={`#${section.id}`}>
                <span className="toc-n">{index + 1}</span>
                <span>{section.title}</span>
              </a>
            </li>
          ))}
        </ol>
      </details>
    </nav>
  );
}

/**
 * A legal document (C-159): a page head with the dates, then the summary, the contents (sticky
 * beside the text on a wide screen, with the section being read marked) and the numbered sections.
 * A reading bar along the top edge follows the scroll (CSS scroll timeline, no script). Server-
 * rendered; TocSpy is the only client code and loads at an idle moment.
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
    <main id="main" tabIndex={-1} className="legal flex-1 outline-none">
      <div className="read-bar" aria-hidden />
      <header className="page-head legal-head">
        <div className="wrap">
          <p className={SECTION_EYEBROW}>Legal</p>
          <h1 className="h-page">{title}</h1>
          <LegalDates document={document} />
        </div>
      </header>

      <div className="wrap">
        <div className="legal-grid">
          <section data-legal-summary="" aria-label="Summary" className="legal-sum">
            <p className="legal-sum-h">
              <Ico icon={ListChecks} />
              Summary
            </p>
            <div className="legal-sum-b">{summary}</div>
          </section>

          <aside className="legal-side">
            <LegalContents sections={sections} />
          </aside>

          <div data-legal-prose="" className="lprose legal-prose">
            {sections.map((section, index) => (
              <section key={section.id} aria-labelledby={section.id} className="lsec">
                <h2 id={section.id}>
                  <span className="lsec-n">{index + 1}.</span> {section.title}
                </h2>
                {section.body}
              </section>
            ))}
          </div>
        </div>
      </div>
      <TocSpy />
    </main>
  );
}
