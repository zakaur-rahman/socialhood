import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LegalDates, LegalFacts } from "@/components/marketing/legal/LegalPage";

import { LEGAL, governingLawClause, legalDate, legalFacts, operatorName, type LegalConfig } from "./legal";

const EMPTY: LegalConfig = { contactEmail: "support@socialhood.com" };
const FULL: LegalConfig = {
  entityName: "Example Technologies Private Limited",
  registeredAddress: "12 Example Road, Bengaluru 560001, India",
  governingLaw: "the laws of India",
  jurisdiction: "the courts at Bengaluru, Karnataka",
  effectiveDate: "2026-10-15",
  grievanceOfficer: { name: "A. Person", email: "privacy@socialhood.com" },
  contactEmail: "support@socialhood.com",
};

// Anything that would read as an unfilled template on a public page.
const PLACEHOLDER = /\[[^\]]*\]|undefined|null|TODO|TBD|\{\{/;

describe("the legal config renders only what is set", () => {
  it("today's config sets nothing but the contact email", () => {
    expect(LEGAL.entityName).toBeUndefined();
    expect(legalFacts(LEGAL)).toEqual([{ label: "Email", value: "support@socialhood.com", href: "mailto:support@socialhood.com" }]);
    expect(operatorName(LEGAL)).toBe("Social Hood");
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
    expect(screen.queryByText("Grievance officer")).not.toBeInTheDocument();
    expect(screen.queryByText(/Effective/)).not.toBeInTheDocument();
    expect(screen.getByText("Last updated 1 October 2026")).toBeInTheDocument();
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
    expect(terms).toEqual(["Operated by", "Registered address", "Email", "Grievance officer"]);
    expect(screen.getByText("Example Technologies Private Limited")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "A. Person, privacy@socialhood.com" })).toHaveAttribute(
      "href",
      "mailto:privacy@socialhood.com",
    );
    expect(screen.getByText(/Effective 15 October 2026/)).toBeInTheDocument();
    expect(governingLawClause(FULL)).toBe(
      "These terms are governed by the laws of India. Disputes about them are decided by the courts at Bengaluru, Karnataka.",
    );
    expect(governingLawClause({ ...EMPTY, jurisdiction: "the courts at Mumbai" })).toBe(
      "Disputes about them are decided by the courts at Mumbai.",
    );
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

  it("with today's config: no placeholders, no governing-law clause, a Last updated date", async () => {
    for (const path of ["privacy", "terms", "refunds"] as const) {
      const { default: Page } = await import(`../app/(marketing)/${path}/page.tsx`);
      const { container, unmount } = render(<Page />);
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
      expect(screen.getByText("Last updated 1 October 2026")).toBeInTheDocument();
      expect(container.textContent).not.toMatch(PLACEHOLDER);
      expect(screen.queryByRole("heading", { name: /Governing law/ })).not.toBeInTheDocument();
      expect(screen.queryByText("Operated by")).not.toBeInTheDocument();
      unmount();
    }
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
