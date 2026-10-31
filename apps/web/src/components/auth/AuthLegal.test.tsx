import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LEGAL_DOCUMENTS } from "@/lib/legal";

import { AuthLegal, authLegalLinks } from "./AuthLegal";
import { AuthShell } from "./AuthShell";

afterEach(() => vi.unstubAllEnvs());

describe("authLegalLinks (C-158)", () => {
  it("names the public Terms and Privacy pages from LEGAL_DOCUMENTS", () => {
    const { terms, privacy } = authLegalLinks(null);
    expect(terms).toEqual({ href: LEGAL_DOCUMENTS.terms.path, title: LEGAL_DOCUMENTS.terms.title });
    expect(privacy).toEqual({ href: LEGAL_DOCUMENTS.privacy.path, title: LEGAL_DOCUMENTS.privacy.title });
  });

  it("points at the public site's origin, never the app host, when the app has its own", () => {
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://amplychat.com");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://dashboard.amplychat.com");
    const { terms, privacy } = authLegalLinks();
    expect(terms.href).toBe("https://amplychat.com/terms");
    expect(privacy.href).toBe("https://amplychat.com/privacy");
  });

  it("stays relative with one origin (local dev, e2e)", () => {
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "");
    expect(authLegalLinks().terms.href).toBe("/terms");
  });
});

describe("AuthLegal", () => {
  it("sign-in: a quiet 'Terms · Privacy' line, opening in a new tab", () => {
    render(<AuthLegal mode="sign-in" />);
    const nav = screen.getByRole("navigation", { name: "Legal" });
    expect(nav).toHaveTextContent(/^Terms.*·\s*Privacy/);
    const terms = within(nav).getByRole("link", { name: /^Terms/ });
    const privacy = within(nav).getByRole("link", { name: /^Privacy/ });
    expect(terms).toHaveAttribute("href", "/terms");
    expect(privacy).toHaveAttribute("href", "/privacy");
    expect(terms).toHaveAttribute("target", "_blank");
    expect(terms).toHaveTextContent(/^Terms\s*\(opens in a new tab\)$/);
  });

  it("sign-up: the consent sentence, and the short line for when Clerk shows its own checkbox", () => {
    render(<AuthLegal mode="sign-up" />);
    const nav = screen.getByRole("navigation", { name: "Legal" });
    const fallback = nav.querySelector('[data-legal-line="fallback"]');
    const withConsent = nav.querySelector('[data-legal-line="with-consent"]');
    // The sentence as seen (the links' "(opens in a new tab)" is for screen readers only).
    expect(fallback?.textContent?.replace(/\s*\(opens in a new tab\)/g, "")).toBe(
      "By continuing, you agree to our Terms and Privacy Policy.",
    );
    // CSS swaps the two (group-has on Clerk's #legalAccepted-field): never both on screen.
    expect(fallback?.className).toContain("group-has-[#legalAccepted-field]/auth:hidden");
    expect(withConsent?.className).toMatch(/(^|\s)hidden(\s|$)/);
    expect(withConsent?.className).toContain("group-has-[#legalAccepted-field]/auth:block");
    for (const link of within(nav).getAllByRole("link", { name: /^Terms/ })) expect(link).toHaveAttribute("href", "/terms");
    for (const link of within(nav).getAllByRole("link", { name: /^Privacy/ })) expect(link).toHaveAttribute("href", "/privacy");
  });
});

describe("AuthShell", () => {
  it.each(["sign-in", "sign-up"] as const)("%s: the legal line is on the page, inside the swap group", (mode) => {
    render(
      <AuthShell mode={mode}>
        <div>card</div>
      </AuthShell>,
    );
    const main = screen.getByRole("main");
    expect(main.className).toContain("group/auth");
    expect(within(main).getByRole("navigation", { name: "Legal" })).toBeInTheDocument();
    // One logo link back to the public site's home on small screens and one in the wide panel.
    expect(within(main).getAllByRole("link", { name: "Amplychat" }).every((a) => a.getAttribute("href") === "/")).toBe(true);
    // The page's h1 is Clerk's card title: the shell adds none.
    expect(within(main).queryByRole("heading", { level: 1 })).toBeNull();
  });
});
