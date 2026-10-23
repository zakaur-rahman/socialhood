import type { ConsentChannel, ContactFilterSpec, LeadStage, Platform } from "@/lib/api/types";

/** Last activity as a moving range: the API takes days, so a saved segment stays current. */
export type ActivityRange = "any" | "7d" | "30d" | "90d" | "quiet30" | "quiet90";

export const ACTIVITY_RANGES: { value: ActivityRange; label: string }[] = [
  { value: "any", label: "Any time" },
  { value: "7d", label: "Active in the last 7 days" },
  { value: "30d", label: "Active in the last 30 days" },
  { value: "90d", label: "Active in the last 90 days" },
  { value: "quiet30", label: "Quiet for 30 days or more" },
  { value: "quiet90", label: "Quiet for 90 days or more" },
];

/** A custom field condition: the field has any value, or equals one (ignoring case). */
export type FieldFilter = { key: string; mode: "has" | "equals"; value: string };

/** The contacts page's filters (GR-17). Part of the list's query key. */
export type ContactFilters = {
  q: string;
  tagIds: string[];
  platform: Platform | null;
  hasEmail: boolean | null;
  hasPhone: boolean | null;
  consent: ConsentChannel | null;
  minLeadScore: number | null;
  /** Lead stages (GR-18): a contact in any of them. Empty: every stage. */
  stages: LeadStage[];
  activity: ActivityRange;
  fields: FieldFilter[];
};

export const EMPTY_FILTERS: ContactFilters = {
  q: "",
  tagIds: [],
  platform: null,
  hasEmail: null,
  hasPhone: null,
  consent: null,
  minLeadScore: null,
  stages: [],
  activity: "any",
  fields: [],
};

export const MAX_TAG_FILTERS = 10;
export const MAX_FIELD_FILTERS = 5;

const DAYS: Record<Exclude<ActivityRange, "any">, { within?: number; quiet?: number }> = {
  "7d": { within: 7 },
  "30d": { within: 30 },
  "90d": { within: 90 },
  quiet30: { quiet: 30 },
  quiet90: { quiet: 90 },
};

/** A field condition as the API writes it: `city:pune` or `city:*`. Incomplete rows are dropped. */
export function fieldMatches(fields: readonly FieldFilter[]): string[] {
  return fields
    .filter((f) => f.key && (f.mode === "has" || f.value.trim() !== ""))
    .slice(0, MAX_FIELD_FILTERS)
    .map((f) => `${f.key}:${f.mode === "has" ? "*" : f.value.trim()}`);
}

/** The filters as the saved shape, for a segment and for tagging everything that matches. */
export function filtersToSpec(f: ContactFilters): ContactFilterSpec {
  const range = f.activity === "any" ? {} : DAYS[f.activity];
  const spec: ContactFilterSpec = {};
  if (f.q.trim()) spec.q = f.q.trim();
  if (f.tagIds.length) spec.tag_ids = f.tagIds.slice(0, MAX_TAG_FILTERS);
  if (f.platform) spec.platform = f.platform as "instagram" | "whatsapp";
  if (f.hasEmail !== null) spec.has_email = f.hasEmail;
  if (f.hasPhone !== null) spec.has_phone = f.hasPhone;
  if (f.consent) spec.marketing_consent = f.consent;
  if (f.minLeadScore !== null) spec.min_lead_score = f.minLeadScore;
  if (f.stages.length) spec.stages = f.stages;
  if (range.within) spec.active_within_days = range.within;
  if (range.quiet) spec.inactive_for_days = range.quiet;
  const fields = fieldMatches(f.fields);
  if (fields.length) spec.fields = fields;
  return spec;
}

/** The list, count and export routes take the same keys as query parameters. */
export function filtersToQuery(f: ContactFilters) {
  const spec = filtersToSpec(f);
  return {
    q: spec.q,
    tag_id: spec.tag_ids,
    platform: spec.platform,
    has_email: spec.has_email,
    has_phone: spec.has_phone,
    marketing_consent: spec.marketing_consent,
    min_lead_score: spec.min_lead_score,
    stage: spec.stages,
    active_within_days: spec.active_within_days,
    inactive_for_days: spec.inactive_for_days,
    field: spec.fields,
  };
}

/** A saved segment as page filters. A date range saved by an API client has no control here, so it
 * is left out of the page's view of the segment. */
export function specToFilters(spec: ContactFilterSpec): ContactFilters {
  let activity: ActivityRange = "any";
  if (spec.active_within_days) {
    activity = spec.active_within_days <= 7 ? "7d" : spec.active_within_days <= 30 ? "30d" : "90d";
  } else if (spec.inactive_for_days) {
    activity = spec.inactive_for_days <= 30 ? "quiet30" : "quiet90";
  }
  return {
    q: spec.q ?? "",
    tagIds: spec.tag_ids ?? [],
    platform: (spec.platform as Platform | null | undefined) ?? null,
    hasEmail: spec.has_email ?? null,
    hasPhone: spec.has_phone ?? null,
    consent: spec.marketing_consent ?? null,
    minLeadScore: spec.min_lead_score ?? null,
    stages: spec.stages ?? [],
    activity,
    fields: (spec.fields ?? []).map((match) => {
      const at = match.indexOf(":");
      const key = match.slice(0, at);
      const value = match.slice(at + 1);
      return value === "*" ? { key, mode: "has" as const, value: "" } : { key, mode: "equals" as const, value };
    }),
  };
}

/** How many filters are on, for the Filters button (search has its own box). */
export function activeFilterCount(f: ContactFilters): number {
  return (
    f.tagIds.length +
    (f.platform ? 1 : 0) +
    (f.hasEmail !== null ? 1 : 0) +
    (f.hasPhone !== null ? 1 : 0) +
    (f.consent ? 1 : 0) +
    (f.minLeadScore !== null ? 1 : 0) +
    (f.stages.length > 0 ? 1 : 0) +
    (f.activity !== "any" ? 1 : 0) +
    fieldMatches(f.fields).length
  );
}

export function hasAnyFilter(f: ContactFilters): boolean {
  return f.q.trim() !== "" || activeFilterCount(f) > 0;
}

/** Whether two filter sets ask for the same contacts (a saved segment shows as active). */
export function sameFilters(a: ContactFilters, b: ContactFilters): boolean {
  return JSON.stringify(filtersToSpec(a)) === JSON.stringify(filtersToSpec(b));
}
