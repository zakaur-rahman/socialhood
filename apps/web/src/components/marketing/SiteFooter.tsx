import type { Route } from "next";
import Link from "next/link";

import { SUPPORT_EMAIL } from "@/lib/copy";
import { LEGAL, operatorName } from "@/lib/legal";
import { LEGAL_LINKS, NAV_LINKS, SIGN_IN_PATH, SIGN_UP_PATH } from "@/lib/marketing/site";

import { Container, Logo } from "./primitives";

const LINK = "inline-flex min-h-10 items-center rounded text-sm text-fg-secondary transition-colors hover:text-fg sm:min-h-8";

/** Product and legal links, the support address, and the copyright line. */
export function SiteFooter({ year = new Date().getFullYear() }: { year?: number }) {
  const product = [
    ...NAV_LINKS,
    { label: "Sign in", href: SIGN_IN_PATH },
    { label: "Start free", href: SIGN_UP_PATH },
  ];
  return (
    <footer className="border-t border-line bg-canvas">
      <Container className="grid gap-10 py-12 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr]">
        <div className="max-w-sm">
          <Logo />
          <p className="mt-3 text-sm leading-relaxed text-fg-secondary">
            One inbox for Instagram and WhatsApp, with AI that answers from your business knowledge.
          </p>
          <p className="mt-4 text-sm">
            <span className="text-fg-secondary">Questions? </span>
            <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-fg underline-offset-4 hover:underline">
              {SUPPORT_EMAIL}
            </a>
          </p>
        </div>
        <nav aria-labelledby="footer-product">
          <h2 id="footer-product" className="text-xs font-semibold tracking-[0.14em] text-fg uppercase">
            Product
          </h2>
          <ul className="mt-3 grid gap-1 sm:gap-1.5">
            {product.map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} prefetch={false} className={LINK}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <nav aria-labelledby="footer-legal">
          <h2 id="footer-legal" className="text-xs font-semibold tracking-[0.14em] text-fg uppercase">
            Legal
          </h2>
          <ul className="mt-3 grid gap-1 sm:gap-1.5">
            {LEGAL_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href as Route} className={LINK}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </Container>
      <div className="border-t border-line-subtle">
        <Container className="flex flex-col gap-2 py-6 text-xs text-fg-secondary sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {year} {operatorName(LEGAL)}
          </p>
          <p>Connects through Meta&apos;s official APIs. We never ask for your Instagram or Facebook password.</p>
        </Container>
      </div>
    </footer>
  );
}
