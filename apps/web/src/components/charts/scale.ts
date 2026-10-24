/** Axis maths for the chart components: pure, tested directly. */

export type Scale = {
  /** The top of the axis (the bottom is 0: a count, a time or a share starts at zero). */
  top: number;
  /** Tick values from 0 to `top`, evenly spaced. */
  ticks: number[];
};

/**
 * A zero-based axis with round ticks: the step is 1, 2 or 5 times a power of ten, and the top is
 * the first tick at or above the largest value. `fixedTop` pins it (a share runs 0 to 100).
 */
export function niceScale(max: number, fixedTop?: number, wanted = 4): Scale {
  if (fixedTop !== undefined) {
    const step = fixedTop / 2;
    return { top: fixedTop, ticks: [0, step, fixedTop] };
  }
  const safe = max > 0 && Number.isFinite(max) ? max : 1;
  const rough = safe / wanted;
  const power = 10 ** Math.floor(Math.log10(rough));
  const unit = rough / power;
  const step = (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * power;
  const count = Math.max(1, Math.ceil(safe / step - 1e-9));
  const ticks = Array.from({ length: count + 1 }, (_, i) => Number((i * step).toFixed(10)));
  return { top: ticks[count], ticks };
}

/** The x of point `index` of `count` as a percentage of the plot width, inset so end dots stay inside. */
export function xPercent(index: number, count: number, inset = 3): number {
  if (count <= 1) return 50;
  return inset + (index * (100 - inset * 2)) / (count - 1);
}

/** The index of the point nearest to a pointer at `ratio` (0 to 1) across the plot. */
export function nearestIndex(ratio: number, count: number, inset = 3): number {
  if (count <= 1) return 0;
  const percent = Math.min(100, Math.max(0, ratio * 100));
  const raw = ((percent - inset) / (100 - inset * 2)) * (count - 1);
  return Math.min(count - 1, Math.max(0, Math.round(raw)));
}

/** The y of a value as a percentage from the top of the plot. */
export function yPercent(value: number, top: number): number {
  return 100 - (Math.min(value, top) / top) * 100;
}

export type Run = [number, number][];

/** Consecutive points with a value, as [x, y] percentages; a gap ends a run, so no line crosses it. */
export function runsOf(values: readonly (number | null | undefined)[], top: number, inset = 3): Run[] {
  const runs: Run[] = [];
  let current: Run = [];
  values.forEach((value, index) => {
    if (value === null || value === undefined) {
      if (current.length) runs.push(current);
      current = [];
      return;
    }
    current.push([Number(xPercent(index, values.length, inset).toFixed(2)), Number(yPercent(value, top).toFixed(2))]);
  });
  if (current.length) runs.push(current);
  return runs;
}
