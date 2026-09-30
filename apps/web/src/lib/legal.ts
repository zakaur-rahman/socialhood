/**
 * The legal details the Privacy Policy, Terms of Service and Refund Policy need but the code can't
 * know. The owner fills these in (with the lawyer's review, launch checklist §6.4). Every field is
 * optional: the pages render a field only when it is set, so no "[Company]" placeholder is ever
 * shown publicly, and a clause that depends on an unset field (governing law) is left out.
 */
import { SUPPORT_EMAIL } from "@/lib/copy";

export type LegalConfig = {
  /** The registered business that runs Social Hood, e.g. "Example Technologies Private Limited". */
  entityName?: string;
  /** Its registered address, on one line. */
  registeredAddress?: string;
  /** The law the Terms are governed by, e.g. "the laws of India". */
  governingLaw?: string;
  /** Where disputes go, e.g. "the courts at Bengaluru, Karnataka". */
  jurisdiction?: string;
  /** When the documents take effect, as an ISO date ("2026-10-15"). */
  effectiveDate?: string;
  /** DPDP Act: the person who answers privacy questions and grievances, if not the support inbox. */
  grievanceOfficer?: { name?: string; email?: string };
  /** Where people write to us. */
  contactEmail: string;
};

// OWNER REVIEW: fill in before launch; see the report on feature/landing-page.
export const LEGAL: LegalConfig = {
  entityName: undefined,
  registeredAddress: undefined,
  governingLaw: undefined,
  jurisdiction: undefined,
  effectiveDate: undefined,
  grievanceOfficer: undefined,
  contactEmail: SUPPORT_EMAIL,
};

export type LegalDocumentKey = "privacy" | "terms" | "refunds";

/** Each document's page and the date its text last changed (shown as "Last updated"). */
export const LEGAL_DOCUMENTS: Record<LegalDocumentKey, { title: string; path: string; lastUpdated: string }> = {
  privacy: { title: "Privacy Policy", path: "/privacy", lastUpdated: "2026-10-01" },
  terms: { title: "Terms of Service", path: "/terms", lastUpdated: "2026-10-01" },
  // OWNER REVIEW: the refund terms are a default for a monthly SaaS, not a decision yet.
  refunds: { title: "Refund Policy", path: "/refunds", lastUpdated: "2026-10-01" },
};

/** A config value that is really set (not undefined, empty or blank). */
export function isSet(value: string | null | undefined): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

/** "2026-10-01" as "1 October 2026"; null for a value that isn't an ISO date. */
export function legalDate(iso: string | null | undefined): string | null {
  if (!isSet(iso) || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const date = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : DATE.format(date);
}

/** The name we go by in the documents: the legal entity when set, else the product. */
export function operatorName(config: LegalConfig = LEGAL): string {
  return isSet(config.entityName) ? config.entityName.trim() : "Social Hood";
}

export type LegalFact = { label: string; value: string; href?: string };

/** The "who we are" details that are set, in order; unset ones are left out entirely. */
export function legalFacts(config: LegalConfig = LEGAL): LegalFact[] {
  const facts: LegalFact[] = [];
  if (isSet(config.entityName)) facts.push({ label: "Operated by", value: config.entityName.trim() });
  if (isSet(config.registeredAddress)) facts.push({ label: "Registered address", value: config.registeredAddress.trim() });
  if (isSet(config.contactEmail)) {
    facts.push({ label: "Email", value: config.contactEmail.trim(), href: `mailto:${config.contactEmail.trim()}` });
  }
  const officer = config.grievanceOfficer;
  if (officer && (isSet(officer.name) || isSet(officer.email))) {
    const value = [officer.name, officer.email].filter(isSet).map((part) => part.trim()).join(", ");
    facts.push({
      label: "Grievance officer",
      value,
      href: isSet(officer.email) ? `mailto:${officer.email.trim()}` : undefined,
    });
  }
  return facts;
}

/** The governing-law sentence, or null while neither the law nor the courts are set. */
export function governingLawClause(config: LegalConfig = LEGAL): string | null {
  const law = isSet(config.governingLaw) ? config.governingLaw.trim() : null;
  const courts = isSet(config.jurisdiction) ? config.jurisdiction.trim() : null;
  if (!law && !courts) return null;
  const parts: string[] = [];
  if (law) parts.push(`These terms are governed by ${law}.`);
  if (courts) parts.push(`Disputes about them are decided by ${courts}.`);
  return parts.join(" ");
}
