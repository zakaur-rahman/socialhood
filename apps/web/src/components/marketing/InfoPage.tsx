import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { BreadcrumbJsonLd } from "./JsonLd";
import { Ico } from "./landing/Ico";
import { SECTION_EYEBROW } from "./primitives";

export type InfoSection = { id: string; title: string; body: ReactNode };

/**
 * A plain information page on the public site (C-156: /safety, /ai-info, /changelog; C-159 adds
 * /security): the page head with one h1, a lede and optional meta or actions, then the page's own
 * bands (`children`, usually `InfoBand`s), or `sections` set as one reading column, and an optional
 * footer line. Breadcrumbs JSON-LD like every inner page.
 */
export function InfoPage({
  name,
  path,
  eyebrow,
  title,
  lede,
  head,
  sections,
  footer,
  className,
  children,
}: {
  name: string;
  path: string;
  eyebrow: string;
  title: string;
  lede: ReactNode;
  /** Under the lede: the page's actions or meta. */
  head?: ReactNode;
  sections?: InfoSection[];
  footer?: ReactNode;
  /** The page's own wrapper class, to scope its styles. */
  className?: string;
  children?: ReactNode;
}) {
  return (
    <main id="main" tabIndex={-1} className={cn("info flex-1 outline-none", className)}>
      {path ? <BreadcrumbJsonLd name={name} path={path} /> : null}
      <header className="page-head info-head">
        <div className="wrap">
          <p className={SECTION_EYEBROW}>{eyebrow}</p>
          <h1 className="h-page">{title}</h1>
          <p className="lede">{lede}</p>
          {head ? <div className="info-head-x">{head}</div> : null}
        </div>
      </header>
      {sections?.length ? (
        <div className="wrap">
          <div className="lprose info-prose">
            {sections.map((section) => (
              <section key={section.id} id={section.id} aria-labelledby={`${section.id}-title`}>
                <h2 id={`${section.id}-title`}>{section.title}</h2>
                {section.body}
              </section>
            ))}
          </div>
        </div>
      ) : null}
      {children}
      {footer ? (
        <div className="wrap">
          <div className="info-foot">{footer}</div>
        </div>
      ) : null}
    </main>
  );
}

/**
 * One band of an information page (C-159): the heading block on the left (it stays in view on a
 * wide screen, like the landing's security list) and the band's cards or text on the right; one
 * column on a tablet or phone. `night` makes it a night band (a page's closing moment).
 */
export function InfoBand({
  id,
  title,
  icon,
  intro,
  night = false,
  wide = false,
  className,
  children,
}: {
  id: string;
  title: ReactNode;
  icon?: LucideIcon;
  intro?: ReactNode;
  night?: boolean;
  /** The heading above the content instead of beside it, for a band that needs the full width. */
  wide?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={cn("ib-sec", night && "night", className)}>
      <div className="wrap">
        <div className={cn("ib", wide && "ib-wide")}>
          <div className="ib-head">
            {icon ? <Ico icon={icon} /> : null}
            <h2 id={`${id}-title`} className="h-sec">
              {title}
            </h2>
            {intro ? <div className="ib-intro">{intro}</div> : null}
          </div>
          {children ? <div className="ib-body">{children}</div> : null}
        </div>
      </div>
    </section>
  );
}

/** An icon card (the landing's `.fcard`: icon beside the title, the text under it; rise and lift). */
export function InfoCard({
  icon,
  title,
  className,
  iconClassName,
  children,
}: {
  icon: LucideIcon;
  title?: ReactNode;
  className?: string;
  iconClassName?: string;
  children?: ReactNode;
}) {
  return (
    <li className={cn("fcard", !title && "fcard-plain", className)}>
      <Ico icon={icon} className={iconClassName} />
      {title ? <h3>{title}</h3> : null}
      {children}
    </li>
  );
}
