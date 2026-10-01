import { isAbsolute, join, relative, resolve } from "node:path";

/**
 * The tool's settings, from the environment (README.md):
 *
 * - UI_SHOTS_OUT (required): an absolute folder outside the repository; screenshots never go in git.
 * - UI_SHOTS_WIDTHS (optional): a comma list, e.g. "375,1280"; default 375,768,1280,1536.
 * - UI_SHOTS_REDUCED_MOTION=1 (optional): render with prefers-reduced-motion: reduce.
 */

export const ALL_WIDTHS = [375, 768, 1280, 1536] as const;

/** axe runs at these widths only (AGENT_CONTEXT §7). */
export const AXE_WIDTHS = [375, 1280];

export const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** Below this width the app shows the top bar and drawer; touch is emulated below 1024. */
export const PHONE_BELOW = 768;
export const TOUCH_BELOW = 1024;

/** A common screen height for each width (phone, tablet portrait, laptop, large laptop). */
export const HEIGHT: Record<number, number> = { 320: 640, 360: 740, 375: 812, 768: 1024, 1024: 768, 1280: 800, 1440: 900, 1536: 864 };

const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");

export function outDir(): string {
  const value = process.env.UI_SHOTS_OUT;
  if (!value) {
    throw new Error("Set UI_SHOTS_OUT to an absolute folder outside the repository (see scripts/ui-shots/README.md).");
  }
  if (!isAbsolute(value)) throw new Error(`UI_SHOTS_OUT must be an absolute path, not "${value}".`);
  const fromRepo = relative(REPO_ROOT, resolve(value));
  if (!fromRepo.startsWith("..") && !isAbsolute(fromRepo)) {
    throw new Error(`UI_SHOTS_OUT must be outside the repository (${REPO_ROOT}); screenshots are never committed.`);
  }
  return resolve(value);
}

export function widths(): number[] {
  const value = process.env.UI_SHOTS_WIDTHS;
  if (!value) return [...ALL_WIDTHS];
  const list = value.split(",").map((part) => Number(part.trim()));
  if (list.some((n) => !Number.isInteger(n) || n < 280 || n > 3840)) {
    throw new Error(`UI_SHOTS_WIDTHS must be a comma list of widths in px, not "${value}".`);
  }
  return [...new Set(list)];
}

export function reducedMotion(): "reduce" | "no-preference" {
  return process.env.UI_SHOTS_REDUCED_MOTION === "1" ? "reduce" : "no-preference";
}

export const axeDir = () => join(outDir(), "axe");
export const metaDir = () => join(outDir(), "meta");
