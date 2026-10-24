import { describe, expect, it } from "vitest";

import type { GoogleSheetColumn, GoogleSheetFieldOption } from "@/lib/api/types";

import {
  MAX_COLUMNS,
  addColumn,
  canSave,
  fieldLabel,
  moveColumn,
  removeColumn,
  renameColumn,
  sameColumns,
  unusedFields,
} from "./sheetMapping";

const OPTIONS: GoogleSheetFieldOption[] = [
  { field: "contact_name", label: "Name", custom: false },
  { field: "email", label: "Email", custom: false },
  { field: "phone", label: "Phone", custom: false },
  { field: "field:city", label: "City", custom: true },
];
const COLUMNS: GoogleSheetColumn[] = [
  { field: "contact_name", header: "Name" },
  { field: "email", header: "Mail" },
];

describe("sheet mapping helpers (GR-27)", () => {
  it("moves a column and leaves the ends alone", () => {
    expect(moveColumn(COLUMNS, 1, -1).map((c) => c.field)).toEqual(["email", "contact_name"]);
    expect(moveColumn(COLUMNS, 0, 1).map((c) => c.field)).toEqual(["email", "contact_name"]);
    expect(moveColumn(COLUMNS, 0, -1)).toBe(COLUMNS);
    expect(moveColumn(COLUMNS, 1, 1)).toBe(COLUMNS);
  });

  it("renames and removes without changing the original", () => {
    expect(renameColumn(COLUMNS, 1, "Email address")[1]).toEqual({ field: "email", header: "Email address" });
    expect(removeColumn(COLUMNS, 0)).toEqual([{ field: "email", header: "Mail" }]);
    expect(COLUMNS).toHaveLength(2);
  });

  it("adds a field once, headed with its label", () => {
    const added = addColumn(COLUMNS, OPTIONS[3]);
    expect(added[2]).toEqual({ field: "field:city", header: "City" });
    expect(addColumn(added, OPTIONS[3])).toBe(added);
  });

  it("stops at the column limit", () => {
    const full = Array.from({ length: MAX_COLUMNS }, (_, i) => ({ field: `field:k${i}`, header: `K${i}` }));
    expect(addColumn(full, OPTIONS[2])).toBe(full);
  });

  it("lists the fields without a column", () => {
    expect(unusedFields(OPTIONS, COLUMNS).map((o) => o.field)).toEqual(["phone", "field:city"]);
  });

  it("compares columns by field and header", () => {
    expect(sameColumns(COLUMNS, [...COLUMNS])).toBe(true);
    expect(sameColumns(COLUMNS, renameColumn(COLUMNS, 0, "Who"))).toBe(false);
    expect(sameColumns(COLUMNS, moveColumn(COLUMNS, 0, 1))).toBe(false);
  });

  it("names a field, falling back to its key", () => {
    expect(fieldLabel(OPTIONS, "field:city")).toBe("City");
    expect(fieldLabel(OPTIONS, "field:gone")).toBe("field:gone");
  });

  it("needs a header on every column", () => {
    expect(canSave(COLUMNS)).toBe(true);
    expect(canSave(renameColumn(COLUMNS, 0, "  "))).toBe(false);
    expect(canSave([])).toBe(false);
  });
});
