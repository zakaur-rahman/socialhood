/** Keyword chips (FR-AUT-01, FR-AUT-06): 1–50 per automation, compared as the matcher does. */

export const MAX_KEYWORDS = 50;
export const KEYWORD_MAX_LENGTH = 100;

/** NFKC, case-folded, whitespace collapsed: two keywords equal here match the same messages. */
export function normalizeKeyword(keyword: string): string {
  return keyword.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
}

/** A pasted list: commas, semicolons, tabs and new lines all separate keywords. */
export function splitKeywords(text: string): string[] {
  return text
    .split(/[,;\t\r\n]+/)
    .map((part) => part.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

export type AddResult = {
  keywords: string[];
  /** Already in the list, compared normalised. */
  duplicates: string[];
  /** Left out because the list is full. */
  overflow: string[];
};

export function addKeywords(existing: string[], incoming: string[]): AddResult {
  const seen = new Set(existing.map(normalizeKeyword));
  const keywords = [...existing];
  const duplicates: string[] = [];
  const overflow: string[] = [];
  for (const raw of incoming) {
    const keyword = raw.slice(0, KEYWORD_MAX_LENGTH).trim();
    if (!keyword) continue;
    const key = normalizeKeyword(keyword);
    if (seen.has(key)) {
      duplicates.push(keyword);
      continue;
    }
    if (keywords.length >= MAX_KEYWORDS) {
      overflow.push(keyword);
      continue;
    }
    seen.add(key);
    keywords.push(keyword);
  }
  return { keywords, duplicates, overflow };
}
