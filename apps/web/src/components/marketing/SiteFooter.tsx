import type { Route } from "next";
import Link from "next/link";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { LEGAL, operatorName } from "@/lib/legal";
import { LEARN_LINKS, LEGAL_LINKS, NAV_LINKS, SIGN_IN_PATH, SIGN_UP_PATH, appUrl } from "@/lib/marketing/site";

import { Logo } from "./primitives";

/** Product, compare and legal links, the support address and the copyright line, on a night band (C-155). */
export function SiteFooter({ year = new Date().getFullYear() }: { year?: number }) {
  const product = [
    ...NAV_LINKS,
    { label: "Sign in", href: appUrl(SIGN_IN_PATH) },
    { label: "Start free", href: appUrl(SIGN_UP_PATH) },
  ];
  return (
    <footer className="night foot">
      <div className="wrap">
        <div className="foot-grid">
          <div>
            <Logo />
            <p className="about">One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.</p>
            <p className="about">
              Questions? <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
            </p>
          </div>
          <nav aria-labelledby="footer-product">
            <h2 id="footer-product">Product</h2>
            <ul>
              {product.map((link) => (
                <li key={link.href}>
                  <Link href={link.href as Route} prefetch={false}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-labelledby="footer-learn">
            <h2 id="footer-learn">Compare and learn</h2>
            <ul>
              {LEARN_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href as Route} lang={link.lang}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-labelledby="footer-legal">
            <h2 id="footer-legal">Legal</h2>
            <ul>
              {LEGAL_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href as Route}>{link.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="foot-bot">
          <p>
            © {year} {operatorName(LEGAL)}
          </p>
          <p>Connects through Meta&apos;s official APIs. We never ask for your Instagram or Facebook password.</p>
        </div>
      </div>
    </footer>
  );
}
