import { cx } from "@/lib/cx";
import { LEGAL_DOCUMENTS } from "@/lib/legal";
import { siteHref } from "@/lib/marketing/site";

export type AuthMode = "sign-in" | "sign-up";

/**
 * The Terms and the Privacy Policy as the auth pages link them (C-158): the public site's pages, from
 * `LEGAL_DOCUMENTS`, on the site's origin when the app has its own host (`siteHref`), never the app
 * host. With one origin (local dev, e2e) the paths stay relative.
 */
export function authLegalLinks(origin?: string | null) {
  const href = (path: string) => (origin === undefined ? siteHref(path) : siteHref(path, origin));
  return {
    terms: { href: href(LEGAL_DOCUMENTS.terms.path), title: LEGAL_DOCUMENTS.terms.title },
    privacy: { href: href(LEGAL_DOCUMENTS.privacy.path), title: LEGAL_DOCUMENTS.privacy.title },
  };
}

/** A legal link: opens in a new tab, so a half-filled form isn't lost. */
function LegalLink({ href, children }: { href: string; children: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      className="rounded-sm underline decoration-line-control underline-offset-4 transition-colors duration-fast hover:text-fg hover:decoration-current"
    >
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/**
 * The quiet legal line under the card, always visible (C-158).
 *
 * - Sign-in: "Terms · Privacy".
 * - Sign-up: "By continuing, you agree to our Terms and Privacy Policy." while Clerk's "Require
 *   express consent to legal documents" is off. When it is on, Clerk renders its own checkbox ("I
 *   agree to the Terms of Service and Privacy Policy"), and the sentence would say the same thing
 *   twice, so the line becomes "Terms · Privacy" like sign-in's. The swap is CSS only: the shell is a
 *   `group/auth`, and Clerk's checkbox input is `#legalAccepted-field`, so `group-has-[…]` reads
 *   whether the card shows it. No script, and it follows each step of the flow (the checkbox is on
 *   the first step only; later steps, such as the email code, show the short line's fallback again).
 */
export function AuthLegal({ mode, className }: { mode: AuthMode; className?: string }) {
  const { terms, privacy } = authLegalLinks();
  const short = (
    <>
      <LegalLink href={terms.href}>Terms</LegalLink>
      <span aria-hidden className="mx-2">
        ·
      </span>
      <LegalLink href={privacy.href}>Privacy</LegalLink>
    </>
  );
  const base = cx("text-site-caption text-fg-secondary", className);

  if (mode === "sign-in") {
    return (
      <nav aria-label="Legal" data-auth-legal="sign-in" className={base}>
        <p>{short}</p>
      </nav>
    );
  }
  return (
    <nav aria-label="Legal" data-auth-legal="sign-up" className={base}>
      <p data-legal-line="fallback" className="text-pretty group-has-[#legalAccepted-field]/auth:hidden">
        By continuing, you agree to our <LegalLink href={terms.href}>Terms</LegalLink> and{" "}
        <LegalLink href={privacy.href}>Privacy Policy</LegalLink>.
      </p>
      <p data-legal-line="with-consent" className="hidden group-has-[#legalAccepted-field]/auth:block">
        {short}
      </p>
    </nav>
  );
}
