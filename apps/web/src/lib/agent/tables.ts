/**
 * Presentation of the generic table visual (VIS-09). Cells are the tool's own text and figures;
 * this formats them by their column. Pure, tested directly.
 */
import type { TableColumn, TableVisual } from "@/lib/api/types";

import { formatValue, NONE } from "./visuals";

/** A cell as text: a figure by its column's format, text as it is, a missing value as a dash. */
export function cellText(value: string | number | null | undefined, column: Pick<TableColumn, "format">): string {
  if (value === null || value === undefined || value === "") return NONE;
  if (typeof value === "number") return formatValue(column.format === "percent" ? "percent" : "count", value);
  return value;
}

/** How many more rows exist than the table shows, or 0. */
export function moreRows(visual: Pick<TableVisual, "total" | "rows">): number {
  return Math.max(visual.total - visual.rows.length, 0);
}
