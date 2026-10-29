import type { Route } from "next";
import Link from "next/link";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { LEGAL, operatorName, publicLocation } from "@/lib/legal";
import { SITE_NAME, footerColumns, type FooterLink } from "@/lib/marketing/site";

import { Logo } from "./primitives";

function FooterItem({ link }: { link: FooterLink }) {
  // The status page and an app link on its own host are other origins: a plain link, no prefetch.
  if (link.external || /^https?:/.test(link.href)) {
    return (
      <a href={link.href} rel={link.external ? "noopener" : undefined}>
        {link.label}
      </a>
    );
  }
  return (
    <Link href={link.href as Route} prefetch={false}>
      {link.label}
    </Link>
  );
}

/**
 * The footer on a night band (C-155, columns C-156): product, solutions, comparisons, resources,
 * and legal and trust links; the support address; the business, its state and country, the
 * official-API line and the Meta trademark note. Status appears only when NEXT_PUBLIC_STATUS_URL is
 * set. No social links until the business has profiles.
 */
export function SiteFooter({ year = new Date().getFullYear(), status }: { year?: number; status?: string | null }) {
  const columns = footerColumns(status);
  return (
    <footer className="night foot">
      <div className="wrap">
        <div className="foot-grid">
          <div className="foot-about">
            <Logo />
            <p className="about">One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.</p>
            <p className="about">
              Questions? <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
            </p>
          </div>
          {columns.map((column) => (
            <nav key={column.id} aria-labelledby={`footer-${column.id}`}>
              <h2 id={`footer-${column.id}`}>{column.title}</h2>
              <ul>
                {column.links.map((link) => (
                  <li key={link.href}>
                    <FooterItem link={link} />
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>
        <div className="foot-bot">
          <p>
            © {year} {operatorName(LEGAL)} · {publicLocation()}
          </p>
          <p>Connects through Meta&apos;s official APIs. We never ask for your Instagram or Facebook password.</p>
          <p className="foot-fine">
            {SITE_NAME} isn&apos;t affiliated with or endorsed by Meta. Instagram and WhatsApp are trademarks of Meta Platforms, Inc.
          </p>
        </div>
      </div>
    </footer>
  );
}
