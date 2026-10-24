/**
 * The categorical chart palette: `--color-chart-series-1` to `-6` (globals.css), in a fixed order
 * that is never cycled. A chart colours an entity (an account, a platform, a topic) by its
 * position in a list that does not depend on what is on screen, so a filter that drops a series
 * never repaints the others. Past six entities the rest are folded into "Other" in the neutral
 * token, or the chart is split; a seventh hue is never invented.
 *
 * The class strings are written out in full so Tailwind sees them. Components use these (and the
 * positive/neutral/negative tokens for sentiment) and never a raw colour.
 */
export type SeriesStyle = {
  /** A filled mark: a legend key, a bar, a dot. */
  bg: string;
  /** A line. */
  line: string;
  /** `currentColor` for an svg that draws with it. */
  text: string;
};

export const SERIES_STYLES: readonly SeriesStyle[] = [
  { bg: "bg-chart-series-1", line: "stroke-chart-series-1", text: "text-chart-series-1" },
  { bg: "bg-chart-series-2", line: "stroke-chart-series-2", text: "text-chart-series-2" },
  { bg: "bg-chart-series-3", line: "stroke-chart-series-3", text: "text-chart-series-3" },
  { bg: "bg-chart-series-4", line: "stroke-chart-series-4", text: "text-chart-series-4" },
  { bg: "bg-chart-series-5", line: "stroke-chart-series-5", text: "text-chart-series-5" },
  { bg: "bg-chart-series-6", line: "stroke-chart-series-6", text: "text-chart-series-6" },
];

/** What does not get a hue of its own: "Other", and anything past the sixth series. */
export const NEUTRAL_STYLE: SeriesStyle = {
  bg: "bg-chart-neutral",
  line: "stroke-chart-neutral",
  text: "text-chart-neutral",
};

/** How many entities get a colour of their own. */
export const MAX_SERIES = SERIES_STYLES.length;

/** The style for the entity at `index` in its stable list (neutral past the sixth). */
export function seriesStyle(index: number): SeriesStyle {
  return SERIES_STYLES[index] ?? NEUTRAL_STYLE;
}

/**
 * Each key's position in a stable list, for `seriesStyle`. Pass the list in the order the data
 * source gives it (accounts as the API lists them), not sorted by value or by what is filtered in.
 */
export function colourIndexes(keys: readonly string[]): Map<string, number> {
  return new Map(keys.map((key, index) => [key, index]));
}

/**
 * Colours for a list of entities that has no fixed home (the topics a range happens to rank): each
 * key prefers the place it has in `order` (so "Pricing" is the same hue week after week), and when
 * two shown keys would share a hue the later one takes the next free one. Keys past the sixth hue
 * are neutral. Pass the keys in the order they are shown.
 */
export function assignColours(keys: readonly string[], order: readonly string[]): Map<string, number> {
  const taken = new Set<number>();
  const out = new Map<string, number>();
  for (const key of keys) {
    const found = order.indexOf(key);
    let index = (found < 0 ? out.size : found) % MAX_SERIES;
    for (let tries = 0; tries < MAX_SERIES && taken.has(index); tries += 1) index = (index + 1) % MAX_SERIES;
    if (taken.size >= MAX_SERIES) index = MAX_SERIES; // more keys than hues: neutral
    taken.add(index);
    out.set(key, index);
  }
  return out;
}
