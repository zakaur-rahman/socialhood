import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { BreadcrumbJsonLd } from "./JsonLd";
import { Container, SECTION_EYEBROW } from "./primitives";
import { PROSE } from "./prose";

export type InfoSection = { id: string; title: string; body: ReactNode };

/**
 * A plain information page on the public site (C-156: /safety, /ai-info, /changelog): the page
 * head with one h1 and a lede, then h2 sections in the reading column the legal pages use, and an
 * optional footer line. Breadcrumbs JSON-LD like every inner page.
 */
export function InfoPage({
  name,
  path,
  eyebrow,
  title,
  lede,
  sections,
  footer,
  children,
}: {
  name: string;
  path: string;
  eyebrow: string;
  title: string;
  lede: ReactNode;
  sections?: InfoSection[];
  footer?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <BreadcrumbJsonLd name={name} path={path} />
      <section className="page-head">
        <Container className="max-w-3xl">
          <p className={SECTION_EYEBROW}>{eyebrow}</p>
          <h1 className="h-page">{title}</h1>
          <p className="lede">{lede}</p>
        </Container>
      </section>
      <section className="band">
        <Container className={cn("max-w-3xl space-y-12", PROSE)}>
          {sections?.map((section) => (
            <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`}>
              <h2 id={`${section.id}-title`}>{section.title}</h2>
              {section.body}
            </section>
          ))}
          {children}
          {footer ? <div className="text-sm">{footer}</div> : null}
        </Container>
      </section>
    </main>
  );
}
