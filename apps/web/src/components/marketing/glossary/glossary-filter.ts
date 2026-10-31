/**
 * The glossary index's filter (C-163): shows the terms whose text matches a query and a channel,
 * hides the letter groups left empty, and returns how many terms show. Works on the server-rendered
 * list (`[data-term]` items with `data-text` and `data-channel`, inside `[data-letter]` groups), so the
 * page is complete without script and the island only toggles `hidden`. No layout reads.
 */
export type GlossaryChannelFilter = "all" | "WhatsApp" | "Instagram" | "Meta";

/** Lowercase, accents and punctuation folded, so "opt in" finds "Opt-in" and "inro" finds "Inrō". */
export function fold(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function matches(text: string, channel: string, query: string, wanted: GlossaryChannelFilter): boolean {
  if (wanted !== "all" && channel !== wanted) return false;
  const words = fold(query).split(" ").filter(Boolean);
  const haystack = fold(text);
  return words.every((word) => haystack.includes(word));
}

export function applyGlossaryFilter(root: ParentNode, query: string, wanted: GlossaryChannelFilter): number {
  let shown = 0;
  for (const group of root.querySelectorAll<HTMLElement>("[data-letter]")) {
    let inGroup = 0;
    for (const item of group.querySelectorAll<HTMLElement>("[data-term]")) {
      const show = matches(item.dataset.text ?? "", item.dataset.channel ?? "", query, wanted);
      item.hidden = !show;
      if (show) inGroup += 1;
    }
    group.hidden = inGroup === 0;
    shown += inGroup;
  }
  for (const link of root.querySelectorAll<HTMLElement>("[data-letter-link]")) {
    const group = root.querySelector<HTMLElement>(`[data-letter="${link.dataset.letterLink}"]`);
    link.toggleAttribute("data-empty", !group || group.hidden);
  }
  return shown;
}
