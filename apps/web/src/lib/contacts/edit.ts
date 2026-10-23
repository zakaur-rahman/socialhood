import type { ContactPatch, ContactRecord, FieldDefinition } from "@/lib/api/types";

/** What the edit form holds: every value as the text in its box. */
export type ContactEdit = { email: string; phone: string; fields: Record<string, string> };

/** A stored custom field value as the text in its box. */
export function fieldText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

/** The form's starting values from a contact. */
export function editFrom(record: Pick<ContactRecord, "email" | "phone" | "fields">, definitions: readonly FieldDefinition[]): ContactEdit {
  return {
    email: record.email ?? "",
    phone: record.phone ?? "",
    fields: Object.fromEntries(definitions.map((d) => [d.key, fieldText(record.fields[d.key])])),
  };
}

/**
 * The patch for what changed, or null when nothing did. An emptied email or phone is cleared; an
 * emptied field is removed (null); a number field is sent as a number. The API checks the rest
 * and names each value that does not fit.
 */
export function buildPatch(before: ContactEdit, after: ContactEdit, definitions: readonly FieldDefinition[]): ContactPatch | null {
  const patch: ContactPatch = {};
  const email = after.email.trim();
  if (email !== before.email) {
    if (email === "") patch.clear_email = true;
    else patch.email = email;
  }
  const phone = after.phone.trim();
  if (phone !== before.phone) {
    if (phone === "") patch.clear_phone = true;
    else patch.phone = phone;
  }
  const fields: Record<string, unknown> = {};
  for (const definition of definitions) {
    const was = before.fields[definition.key] ?? "";
    const now = (after.fields[definition.key] ?? "").trim();
    if (now === was) continue;
    if (now === "") fields[definition.key] = null;
    else fields[definition.key] = definition.type === "number" && !Number.isNaN(Number(now)) ? Number(now) : now;
  }
  if (Object.keys(fields).length > 0) patch.fields = fields;
  return Object.keys(patch).length > 0 ? patch : null;
}
