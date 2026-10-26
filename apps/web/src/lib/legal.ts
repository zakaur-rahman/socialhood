/**
 * The legal details the Privacy Policy, Terms of Service, the refund, shipping and contact pages
 * need but the code can't know. The owner fills these in (with the lawyer's review, launch
 * checklist §6.4). Every field but the email is optional: the pages render a field only when it is
 * set, so no "[Company]" placeholder is ever shown publicly, and a clause that depends on an unset
 * field (governing law) is left out.
 */
import { SUPPORT_EMAIL } from "@/lib/copy";

export type LegalConfig = {
  /**
   * The registered business that runs Amplychat. C-144: written as on its Udyam registration,
   * "UNCHARTD" in capitals, because Meta's business verification compares this name with the
   * registration; one value everywhere (pages, footer, structured data).
   */
  entityName?: string;
  /** What kind of business it is, e.g. "Sole proprietorship registered in India". */
  entityType?: string;
  /** The proprietor of a sole proprietorship. */
  proprietor?: string;
  /** Its registered (and operating) address, on one line. Shown on every legal page once set. */
  registeredAddress?: string;
  /** A phone number customers can call, as it should be shown, e.g. "+91 98765 43210". */
  phone?: string;
  /** The law the Terms are governed by, e.g. "the laws of India". */
  governingLaw?: string;
  /** Where disputes go, e.g. "the courts at Bettiah, Bihar". */
  jurisdiction?: string;
  /** When the documents take effect, as an ISO date ("2026-10-15"). */
  effectiveDate?: string;
  /** DPDP Act: the person who answers privacy questions and grievances, if not the support inbox. */
  grievanceOfficer?: { name?: string; email?: string };
  /**
   * The days we take to answer a grievance. Unset means 30: the IT Rules 2011 (rule 5(9)) ask for
   * one month while they apply, the DPDP Rules (rule 14(3)) for at most 90 days.
   */
  grievanceResponseDays?: number;
  /** How soon support answers an email, e.g. "within 2 working days" (the contact page). */
  supportResponseTime?: string;
  /** Where people write to us. */
  contactEmail: string;
};

// OWNER REVIEW: everything left undefined is an owner decision; see C-144 in docs/CONFLICTS.md for
// the recommended values. Set a field and it appears on the pages; nothing else needs changing.
export const LEGAL: LegalConfig = {
  entityName: "UNCHARTD",
  entityType: "Sole proprietorship registered in India",
  proprietor: "Zakaur Rahman",
  registeredAddress: undefined, // the owner hasn't decided whether to publish it
  phone: undefined,
  governingLaw: undefined,
  jurisdiction: undefined,
  effectiveDate: undefined,
  grievanceOfficer: undefined,
  grievanceResponseDays: undefined,
  supportResponseTime: undefined,
  contactEmail: SUPPORT_EMAIL,
};

export type LegalDocumentKey = "privacy" | "terms" | "refunds" | "shipping";

/** Each document's page and the date its text last changed (shown as "Last updated"). */
export const LEGAL_DOCUMENTS: Record<LegalDocumentKey, { title: string; path: string; lastUpdated: string }> = {
  privacy: { title: "Privacy Policy", path: "/privacy", lastUpdated: "2026-10-26" },
  terms: { title: "Terms of Service", path: "/terms", lastUpdated: "2026-10-26" },
  // OWNER REVIEW: the refund terms are a default for a monthly SaaS, not a decision yet.
  refunds: { title: "Refund and Cancellation Policy", path: "/refunds", lastUpdated: "2026-10-26" },
  shipping: { title: "Shipping and Delivery Policy", path: "/shipping", lastUpdated: "2026-10-26" },
};

/** The most days the DPDP Rules (rule 14(3)) allow for answering a grievance. */
export const GRIEVANCE_DAYS_LIMIT = 90;
/** The default: one month, as the IT Rules 2011 (SPDI, rule 5(9)) ask while they still apply. */
export const GRIEVANCE_DAYS_DEFAULT = 30;

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
  return isSet(config.entityName) ? config.entityName.trim() : "Amplychat";
}

/** The days we promise for a grievance: the configured number, never more than the law allows. */
export function grievanceDays(config: LegalConfig = LEGAL): number {
  const days = config.grievanceResponseDays;
  if (typeof days !== "number" || !Number.isInteger(days) || days < 1) return GRIEVANCE_DAYS_DEFAULT;
  return Math.min(days, GRIEVANCE_DAYS_LIMIT);
}

/** "+91 98765 43210" as a tel: link ("tel:+919876543210"). */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, "")}`;
}

export type LegalFact = { label: string; value: string; href?: string };

/** The "who we are" details that are set, in order; unset ones are left out entirely. */
export function legalFacts(config: LegalConfig = LEGAL): LegalFact[] {
  const facts: LegalFact[] = [];
  if (isSet(config.entityName)) facts.push({ label: "Operated by", value: config.entityName.trim() });
  if (isSet(config.entityType)) facts.push({ label: "Business type", value: config.entityType.trim() });
  if (isSet(config.proprietor)) facts.push({ label: "Proprietor", value: config.proprietor.trim() });
  if (isSet(config.registeredAddress)) facts.push({ label: "Registered address", value: config.registeredAddress.trim() });
  if (isSet(config.phone)) facts.push({ label: "Phone", value: config.phone.trim(), href: telHref(config.phone.trim()) });
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
