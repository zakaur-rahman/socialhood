import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ContactDetails } from "@/components/marketing/legal/ContactDetails";
import { LegalDates, LegalFacts } from "@/components/marketing/legal/LegalPage";
import { SUBPROCESSORS } from "@/lib/subprocessors";

import {
  GRIEVANCE_DAYS_DEFAULT,
  LEGAL,
  LEGAL_DOCUMENTS,
  governingLawClause,
  grievanceDays,
  legalDate,
  legalFacts,
  operatorName,
  telHref,
  type LegalConfig,
} from "./legal";

const EMPTY: LegalConfig = { contactEmail: "support@amplychat.com" };
const FULL: LegalConfig = {
  entityName: "Example Technologies Private Limited",
  entityType: "Private limited company",
  proprietor: "A. Owner",
  registeredAddress: "12 Example Road, Bengaluru 560001, India",
  phone: "+91 98765 43210",
  governingLaw: "the laws of India",
  jurisdiction: "the courts at Bengaluru, Karnataka",
  effectiveDate: "2026-10-15",
  grievanceOfficer: { name: "A. Person", email: "support@amplychat.com" },
  grievanceResponseDays: 21,
  supportResponseTime: "within 2 working days",
  contactEmail: "support@amplychat.com",
};

// Anything that would read as an unfilled template on a public page.
const PLACEHOLDER = /\[[^\]]*\]|undefined|null|TODO|TBD|\{\{/;

describe("the legal config renders only what is set", () => {
  it("today's config: the operator, its type, the proprietor, Bihar, India, the email and the grievance officer's role", () => {
    // C-144: the Udyam legal name, in capitals, so it matches what Meta verifies.
    expect(LEGAL.entityName).toBe("UNCHARTD");
    expect(legalFacts(LEGAL)).toEqual([
      { label: "Operated by", value: "UNCHARTD" },
      { label: "Business type", value: "Sole proprietorship registered in India" },
      { label: "Proprietor", value: "Zakaur Rahman" },
      // C-156: state and country only; the full address is never published.
      { label: "Location", value: "Bihar, India" },
      { label: "Email", value: "support@amplychat.com", href: "mailto:support@amplychat.com" },
      // C-156: a role, not a personal name, at the one support address.
      {
        label: "Grievance officer",
        value: "Grievance Officer, UNCHARTD (support@amplychat.com)",
        href: "mailto:support@amplychat.com",
      },
    ]);
    expect(operatorName(LEGAL)).toBe("UNCHARTD");
    expect(LEGAL.grievanceOfficer?.name).toBeUndefined();
    expect(LEGAL.governingLaw).toBe("the laws of India");
    expect(governingLawClause(LEGAL)).toBe("These terms are governed by the laws of India.");
    expect(legalDate(LEGAL.effectiveDate)).not.toBeNull();
    // Owner decisions stay unset until the owner makes them.
    for (const key of ["registeredAddress", "phone", "jurisdiction"] as const) {
      expect(LEGAL[key]).toBeUndefined();
    }
  });

  it("unset fields leave no label, blank or placeholder", () => {
    const { container } = render(
      <>
        <LegalFacts config={{ ...EMPTY, entityName: "  ", grievanceOfficer: { name: "" } }} />
        <LegalDates document="terms" config={EMPTY} />
      </>,
    );
    expect(screen.queryByText("Operated by")).not.toBeInTheDocument();
    expect(screen.queryByText("Registered address")).not.toBeInTheDocument();
    expect(screen.queryByText("Location")).not.toBeInTheDocument();
    expect(screen.queryByText("Phone")).not.toBeInTheDocument();
    expect(screen.queryByText("Proprietor")).not.toBeInTheDocument();
    expect(screen.queryByText("Grievance officer")).not.toBeInTheDocument();
    expect(screen.queryByText(/Effective/)).not.toBeInTheDocument();
    expect(screen.getByText("Last updated 29 October 2026")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(PLACEHOLDER);
    expect(governingLawClause(EMPTY)).toBeNull();
  });

  it("set fields appear, in order", () => {
    render(
      <>
        <LegalFacts config={FULL} />
        <LegalDates document="privacy" config={FULL} />
      </>,
    );
    const terms = screen.getAllByRole("term").map((node) => node.textContent);
    expect(terms).toEqual([
      "Operated by",
      "Business type",
      "Proprietor",
      "Registered address",
      "Phone",
      "Email",
      "Grievance officer",
    ]);
    expect(screen.getByRole("link", { name: "+91 98765 43210" })).toHaveAttribute("href", "tel:+919876543210");
    expect(screen.getByText("Example Technologies Private Limited")).toBeInTheDocument();
    // A full address wins over the state-and-country location.
    expect(legalFacts({ ...FULL, publicLocation: "Bihar, India" }).map((fact) => fact.label)).not.toContain("Location");
    expect(screen.getByRole("link", { name: "A. Person (support@amplychat.com)" })).toHaveAttribute(
      "href",
      "mailto:support@amplychat.com",
    );
    expect(screen.getByText(/Effective 15 October 2026/)).toBeInTheDocument();
    expect(governingLawClause(FULL)).toBe(
      "These terms are governed by the laws of India. Disputes about them are decided by the courts at Bengaluru, Karnataka.",
    );
    expect(governingLawClause({ ...EMPTY, jurisdiction: "the courts at Mumbai" })).toBe(
      "Disputes about them are decided by the courts at Mumbai.",
    );
  });

  it("grievances are answered within the configured days (one month by default), never more than the law's 90", () => {
    expect(grievanceDays(EMPTY)).toBe(GRIEVANCE_DAYS_DEFAULT);
    expect(grievanceDays({ ...EMPTY, grievanceResponseDays: 15 })).toBe(15);
    expect(grievanceDays({ ...EMPTY, grievanceResponseDays: 120 })).toBe(90);
    expect(grievanceDays({ ...EMPTY, grievanceResponseDays: 0 })).toBe(30);
    expect(telHref("+91 (98765) 43210")).toBe("tel:+919876543210");
  });

  it("dates must be ISO dates", () => {
    expect(legalDate("2026-10-01")).toBe("1 October 2026");
    expect(legalDate("soon")).toBeNull();
    expect(legalDate(undefined)).toBeNull();
  });
});

describe("the legal pages", () => {
  afterEach(() => {
    vi.doUnmock("@/lib/legal");
    vi.resetModules();
  });

  it("with today's config: no placeholders, the dates, the operator named, no full address", async () => {
    const documents = ["privacy", "terms", "refunds", "shipping", "subprocessors", "cookies", "dpa", "accessibility"] as const;
    for (const document of documents) {
      const { default: Page } = await import(`../app/(marketing)/${document}/page.tsx`);
      const { container, unmount } = render(<Page />);
      expect(screen.getByRole("heading", { level: 1, name: LEGAL_DOCUMENTS[document].title })).toBeInTheDocument();
      expect(screen.getByText(new RegExp(`Last updated ${legalDate(LEGAL_DOCUMENTS[document].lastUpdated)}`))).toBeInTheDocument();
      expect(screen.getByText(/Effective 30 October 2026/)).toBeInTheDocument();
      expect(container.textContent).not.toMatch(PLACEHOLDER);
      // C-156: governing law is set, so only Terms has the section; no courts are named.
      const law = screen.queryByRole("heading", { name: /Governing law/ });
      if (document === "terms") expect(law).toBeInTheDocument();
      else expect(law).not.toBeInTheDocument();
      expect(container.textContent).not.toMatch(/Disputes about them are decided/);
      expect(screen.queryByText("Registered address")).not.toBeInTheDocument();
      expect(screen.queryByText("Phone")).not.toBeInTheDocument();
      // C-139, C-144: the operator, UNCHARTD, is named on each document that shows the facts.
      if (["privacy", "terms", "refunds", "shipping", "dpa"].includes(document)) {
        expect(screen.getAllByText("Operated by").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Bihar, India").length).toBeGreaterThan(0);
      }
      unmount();
    }
  });

  it("the privacy policy, the subprocessors page and the DPA render the one subprocessor list", async () => {
    for (const document of ["privacy", "subprocessors", "dpa"] as const) {
      const { default: Page } = await import(`../app/(marketing)/${document}/page.tsx`);
      const { unmount } = render(<Page />);
      for (const row of SUBPROCESSORS) {
        expect(screen.getByRole("rowheader", { name: row.name })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: row.terms.label })).toHaveAttribute("href", row.terms.href);
      }
      unmount();
    }
    const { default: Privacy } = await import("../app/(marketing)/privacy/page");
    render(<Privacy />);
    expect(screen.getAllByRole("link", { name: "subprocessors page" })[0]).toHaveAttribute("href", "/subprocessors");
    for (const name of ["Everyone", "EEA and UK (GDPR)", "California (CCPA/CPRA)", "India (DPDP Act)"]) {
      expect(screen.getByRole("heading", { level: 3, name })).toBeInTheDocument();
    }
    expect(screen.getAllByText(/Global Privacy Control/).length).toBeGreaterThan(0);
  });

  it("Terms has the AI features section and makes the DPA part of the terms", async () => {
    const { default: TermsPage } = await import("../app/(marketing)/terms/page");
    render(<TermsPage />);
    expect(screen.getByRole("heading", { level: 2, name: /AI features/ })).toBeInTheDocument();
    expect(screen.getByText(/No decisions about people/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Data Processing Agreement" })[0]).toHaveAttribute("href", "/dpa");
    expect(screen.getByRole("link", { name: "subprocessors page" })).toHaveAttribute("href", "/subprocessors");
  });

  it("the cookies page lists the theme cookie and Clerk's, and says why there is no banner", async () => {
    const { default: CookiesPage } = await import("../app/(marketing)/cookies/page");
    render(<CookiesPage />);
    expect(screen.getByText("sh_theme")).toBeInTheDocument();
    expect(screen.getByText("__client")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /No tracking, so no banner/ })).toBeInTheDocument();
  });

  it("once the owner fills the config, Terms names the entity and the governing law", async () => {
    vi.resetModules();
    vi.doMock("@/lib/legal", async (importOriginal) => ({ ...(await importOriginal<typeof import("./legal")>()), LEGAL: FULL }));
    const { default: TermsPage } = await import("../app/(marketing)/terms/page");
    render(<TermsPage />);
    expect(screen.getByRole("heading", { name: /Governing law/ })).toBeInTheDocument();
    expect(screen.getByText(/These terms are governed by the laws of India/)).toBeInTheDocument();
    expect(screen.getAllByText(/Example Technologies Private Limited/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Effective 15 October 2026/)).toBeInTheDocument();
  });
});

describe("the contact page", () => {
  it("with today's config: the business, its type, the proprietor, Bihar, India and the email; no phone or address", async () => {
    const { default: ContactPage } = await import("../app/(marketing)/contact/page");
    const { container } = render(<ContactPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Contact us" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "About us" })).toBeInTheDocument();
    expect(screen.getAllByText("UNCHARTD").length).toBeGreaterThan(0);
    expect(screen.getByText("Zakaur Rahman")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "support@amplychat.com" })[0]).toHaveAttribute(
      "href",
      "mailto:support@amplychat.com",
    );
    expect(screen.queryByText("Phone")).not.toBeInTheDocument();
    expect(screen.queryByText("Registered address")).not.toBeInTheDocument();
    // C-159: the location is a contact card and a fact in "About us".
    expect(screen.getAllByText("Bihar, India")).toHaveLength(2);
    expect(screen.getByRole("heading", { level: 3, name: "Location" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Privacy grievances" })).toBeInTheDocument();
    expect(screen.getByText(/We answer within 30 days/)).toBeInTheDocument();
    expect(screen.queryByText(/We reply within/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Data deletion" })).toHaveAttribute("href", "/data-deletion");
    // C-159: the full FAQ page, not the landing's FAQ band.
    expect(screen.getByRole("link", { name: /Frequently asked questions/ })).toHaveAttribute("href", "/faq");
    // The page's text, without the breadcrumbs JSON-LD it now carries (C-159), whose arrays would read as a placeholder.
    container.querySelectorAll('script[type="application/ld+json"]').forEach((script) => script.remove());
    expect(container.textContent).not.toMatch(PLACEHOLDER);
  });

  it("shows the phone, address and response times once they are set", () => {
    render(<ContactDetails config={FULL} />);
    expect(screen.getAllByRole("link", { name: "+91 98765 43210" })[0]).toHaveAttribute("href", "tel:+919876543210");
    // A full address replaces the location, on the card and in the facts.
    expect(screen.getAllByText("12 Example Road, Bengaluru 560001, India")).toHaveLength(2);
    expect(screen.getByRole("heading", { level: 3, name: "Registered address" })).toBeInTheDocument();
    expect(screen.queryByText("Location")).not.toBeInTheDocument();
    expect(screen.getByText(/We reply within 2 working days/)).toBeInTheDocument();
    expect(screen.getByText(/We answer within 21 days/)).toBeInTheDocument();
    expect(screen.getByText(/a private limited company, owned by A. Owner/)).toBeInTheDocument();
  });
});
