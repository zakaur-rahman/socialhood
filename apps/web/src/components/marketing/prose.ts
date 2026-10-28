import { cn } from "@/lib/utils";
import { READING } from "@/styles/tokens";

/**
 * Prose styles for long text on the public site (no typography plugin): headings, paragraphs, lists,
 * links and tables. The legal documents and the guides share them. The text is the Reading role,
 * 15/24 (DESIGN_SYSTEM §2.1).
 */
export const PROSE = [
  cn(READING, "text-fg-secondary"),
  "[&_h2]:scroll-mt-24 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-fg",
  "[&_h3]:mt-6 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-fg",
  "[&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5 [&_ol]:mt-3 [&_ol]:list-decimal [&_ol]:space-y-1.5 [&_ol]:pl-5",
  "[&_li]:pl-1 [&_strong]:font-semibold [&_strong]:text-fg",
  "[&_a]:font-medium [&_a]:text-brand-fg [&_a]:underline [&_a]:underline-offset-4",
  "[&_table]:mt-4 [&_table]:w-full [&_table]:text-sm [&_th]:border-b [&_th]:border-line [&_th]:py-2 [&_th]:pr-4 [&_th]:text-left [&_th]:font-semibold [&_th]:text-fg",
  "[&_td]:border-b [&_td]:border-line-subtle [&_td]:py-2 [&_td]:pr-4 [&_td]:align-top",
].join(" ");
