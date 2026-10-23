import { describe, expect, it } from "vitest";

import type { FieldDefinition } from "@/lib/api/types";

import { buildPatch, editFrom, fieldText } from "./edit";

const def = (key: string, type: FieldDefinition["type"] = "text"): FieldDefinition => ({
  id: key,
  key,
  label: key,
  type,
  options: type === "choice" ? ["S", "M"] : [],
  position: 0,
});
const defs = [def("city"), def("age", "number"), def("size", "choice")];
const record = { email: "a@example.com", phone: null, fields: { city: "Pune", age: 31 } };

describe("contact edits (GR-17)", () => {
  it("shows stored values as text and missing ones as empty", () => {
    expect(fieldText(31)).toBe("31");
    expect(fieldText(null)).toBe("");
    expect(editFrom(record, defs)).toEqual({
      email: "a@example.com",
      phone: "",
      fields: { city: "Pune", age: "31", size: "" },
    });
  });

  it("makes no patch when nothing changed", () => {
    const before = editFrom(record, defs);
    expect(buildPatch(before, { ...before }, defs)).toBeNull();
  });

  it("sends only what changed", () => {
    const before = editFrom(record, defs);
    const patch = buildPatch(before, { ...before, phone: " 98765 43210 ", fields: { ...before.fields, city: "Goa" } }, defs);
    expect(patch).toEqual({ phone: "98765 43210", fields: { city: "Goa" } });
  });

  it("clears an emptied email, and removes an emptied field", () => {
    const before = editFrom(record, defs);
    const patch = buildPatch(before, { ...before, email: "", fields: { ...before.fields, city: "" } }, defs);
    expect(patch).toEqual({ clear_email: true, fields: { city: null } });
  });

  it("sends a number field as a number and leaves other types as text", () => {
    const before = editFrom(record, defs);
    const patch = buildPatch(before, { ...before, fields: { ...before.fields, age: "32", size: "M" } }, defs);
    expect(patch).toEqual({ fields: { age: 32, size: "M" } });
  });

  it("leaves a number the API should refuse as text, so it names the problem", () => {
    const before = editFrom(record, defs);
    expect(buildPatch(before, { ...before, fields: { ...before.fields, age: "abc" } }, defs)).toEqual({ fields: { age: "abc" } });
  });
});
