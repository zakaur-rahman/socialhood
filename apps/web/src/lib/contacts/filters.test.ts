import { describe, expect, it } from "vitest";

import {
  activeFilterCount,
  EMPTY_FILTERS,
  fieldMatches,
  filtersToQuery,
  filtersToSpec,
  hasAnyFilter,
  sameFilters,
  specToFilters,
  type ContactFilters,
} from "./filters";

const filters = (values: Partial<ContactFilters>): ContactFilters => ({ ...EMPTY_FILTERS, ...values });

describe("contact filters (GR-17)", () => {
  it("sends nothing for no filters", () => {
    expect(filtersToSpec(EMPTY_FILTERS)).toEqual({});
    expect(hasAnyFilter(EMPTY_FILTERS)).toBe(false);
    expect(activeFilterCount(EMPTY_FILTERS)).toBe(0);
  });

  it("turns tag = lead-magnet and has email into the API's keys", () => {
    const f = filters({ tagIds: ["t1"], hasEmail: true });
    expect(filtersToSpec(f)).toEqual({ tag_ids: ["t1"], has_email: true });
    expect(filtersToQuery(f)).toMatchObject({ tag_id: ["t1"], has_email: true });
    expect(activeFilterCount(f)).toBe(2);
  });

  it("keeps a false boolean (no email) apart from not filtering", () => {
    expect(filtersToSpec(filters({ hasEmail: false, hasPhone: false }))).toEqual({ has_email: false, has_phone: false });
  });

  it("writes a field condition as key:value or key:*, and drops an incomplete one", () => {
    const rows = [
      { key: "city", mode: "equals" as const, value: " Pune " },
      { key: "size", mode: "has" as const, value: "" },
      { key: "tier", mode: "equals" as const, value: "  " },
      { key: "", mode: "has" as const, value: "" },
    ];
    expect(fieldMatches(rows)).toEqual(["city:Pune", "size:*"]);
    expect(filtersToSpec(filters({ fields: rows })).fields).toEqual(["city:Pune", "size:*"]);
  });

  it("turns a last activity choice into a moving range in days", () => {
    expect(filtersToSpec(filters({ activity: "7d" }))).toEqual({ active_within_days: 7 });
    expect(filtersToSpec(filters({ activity: "quiet90" }))).toEqual({ inactive_for_days: 90 });
    expect(filtersToQuery(filters({ activity: "30d" })).active_within_days).toBe(30);
  });

  it("trims the search and counts the other filters apart from it", () => {
    const f = filters({ q: "  priya ", platform: "whatsapp", minLeadScore: 0 });
    expect(filtersToSpec(f)).toEqual({ q: "priya", platform: "whatsapp", min_lead_score: 0 });
    expect(activeFilterCount(f)).toBe(2);
    expect(hasAnyFilter(filters({ q: "priya" }))).toBe(true);
  });

  it("reads a saved segment back into the page's filters", () => {
    const f = filters({
      q: "a",
      tagIds: ["t1", "t2"],
      platform: "instagram",
      hasEmail: true,
      consent: "whatsapp",
      minLeadScore: 40,
      activity: "quiet30",
      fields: [
        { key: "city", mode: "equals", value: "Pune" },
        { key: "size", mode: "has", value: "" },
      ],
    });
    expect(specToFilters(filtersToSpec(f))).toEqual(f);
  });

  it("shows a stored range at the nearest control, and values with a colon whole", () => {
    expect(specToFilters({ active_within_days: 14 }).activity).toBe("30d");
    expect(specToFilters({ inactive_for_days: 45 }).activity).toBe("quiet90");
    expect(specToFilters({ fields: ["note:a:b"] }).fields).toEqual([{ key: "note", mode: "equals", value: "a:b" }]);
  });

  it("says whether two filter sets ask for the same contacts", () => {
    expect(sameFilters(filters({ tagIds: ["t1"] }), filters({ tagIds: ["t1"], activity: "any" }))).toBe(true);
    expect(sameFilters(filters({ tagIds: ["t1"] }), filters({ tagIds: ["t2"] }))).toBe(false);
    expect(sameFilters(filters({ q: " x " }), filters({ q: "x" }))).toBe(true);
  });
});
