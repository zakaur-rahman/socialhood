import type { GoogleSheetColumn, GoogleSheetFieldOption } from "@/lib/api/types";

/** The most columns a sheet mapping can hold (the API's limit). */
export const MAX_COLUMNS = 30;

/** Move a column up (-1) or down (+1); a move past either end changes nothing. */
export function moveColumn(columns: GoogleSheetColumn[], index: number, delta: -1 | 1): GoogleSheetColumn[] {
  const target = index + delta;
  if (index < 0 || index >= columns.length || target < 0 || target >= columns.length) return columns;
  const next = [...columns];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function removeColumn(columns: GoogleSheetColumn[], index: number): GoogleSheetColumn[] {
  return columns.filter((_, i) => i !== index);
}

export function renameColumn(columns: GoogleSheetColumn[], index: number, header: string): GoogleSheetColumn[] {
  return columns.map((column, i) => (i === index ? { ...column, header } : column));
}

/** A new last column for a field, headed with the field's own label. */
export function addColumn(columns: GoogleSheetColumn[], option: GoogleSheetFieldOption): GoogleSheetColumn[] {
  if (columns.length >= MAX_COLUMNS || columns.some((c) => c.field === option.field)) return columns;
  return [...columns, { field: option.field, header: option.label }];
}

/** The fields that have no column yet, in the API's order. */
export function unusedFields(options: GoogleSheetFieldOption[], columns: GoogleSheetColumn[]): GoogleSheetFieldOption[] {
  const used = new Set(columns.map((c) => c.field));
  return options.filter((o) => !used.has(o.field));
}

export function sameColumns(a: GoogleSheetColumn[], b: GoogleSheetColumn[]): boolean {
  return a.length === b.length && a.every((c, i) => c.field === b[i].field && c.header === b[i].header);
}

/** The label of a field for the editor ("Email", or a custom field's own name). */
export function fieldLabel(options: GoogleSheetFieldOption[], field: string): string {
  return options.find((o) => o.field === field)?.label ?? field;
}

/** Columns can be saved when there is at least one and each has a header (the API requires one). */
export function canSave(columns: GoogleSheetColumn[]): boolean {
  return columns.length > 0 && columns.every((c) => c.header.trim().length > 0);
}
