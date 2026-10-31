import { ArrowRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { LEGAL, operatorName } from "@/lib/legal";
import { FacebookGlyph } from "@/components/connections/FacebookGlyph";
import { InstagramGlyph } from "@/components/connections/InstagramGlyph";
import { SITE_NAME, SOCIAL_PROFILES, footerColumns, type FooterLink } from "@/lib/marketing/site";

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
 * The footer on a night band (C-155, columns C-156), the second half of the page's closing
 * composition (C-161 v2): a night-line rule opens it, then the brand column (the name, one sentence,
 * "Contact us"), product, solutions, comparisons, resources, and legal and trust (that group across
 * two columns); a quiet bar with the business and the Meta fine print; then the name at full width,
 * decorative. No email and no location here (owner, C-161); /contact and the legal pages carry them.
 * Status appears only when NEXT_PUBLIC_STATUS_URL is set. No social links until the business has
 * profiles.
 */
export function SiteFooter({ year = new Date().getFullYear(), status }: { year?: number; status?: string | null }) {
  const columns = footerColumns(status);
  const operator = operatorName(LEGAL);
  return (
    <footer className="night foot">
      <div className="wrap">
        <div className="foot-grid">
          <div className="foot-about">
            <Logo />
            <p className="about">One inbox for Instagram, WhatsApp and website chat, with AI that answers from your business knowledge.</p>
            <Link href="/contact" prefetch={false} className="foot-contact">
              Contact us <ArrowRight className="size-4" aria-hidden />
            </Link>
            {SOCIAL_PROFILES.length ? (
              <ul className="foot-social" aria-label={`${SITE_NAME} elsewhere`}>
                {SOCIAL_PROFILES.map((profile) => (
                  <li key={profile.url}>
                    <a href={profile.url} rel="me noopener noreferrer" target="_blank" aria-label={`${SITE_NAME} on ${profile.label} (opens in a new tab)`}>
                      {profile.network === "instagram" ? <InstagramGlyph className="size-5" /> : <FacebookGlyph className="size-5" />}
                    </a>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          {columns.map((column) => (
            <nav key={column.id} aria-labelledby={`footer-${column.id}`} className={column.id === "legal" ? "foot-two" : undefined}>
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
          <p className="foot-copy">
            <span>
              © {year} {operator}.
            </span>
            {operator !== SITE_NAME && (
              <>
                {" "}
                <span>
                  {SITE_NAME} is a product of {operator}.
                </span>
              </>
            )}
          </p>
          <div className="foot-legal">
            <p>Connects through Meta&apos;s official APIs. We never ask for your Instagram or Facebook password.</p>
            <p className="foot-fine">
              {SITE_NAME} isn&apos;t affiliated with or endorsed by Meta. Instagram and WhatsApp are trademarks of Meta Platforms, Inc.
            </p>
          </div>
        </div>
        <p className="foot-word" aria-hidden>
          {SITE_NAME}
        </p>
      </div>
    </footer>
  );
}
