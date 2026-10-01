import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { BREAKPOINTS, minWidth } from "./breakpoints";

/** The rem value CSS gives `--breakpoint-<name>`: Tailwind's theme, or our addition in globals.css. */
function cssBreakpointPx(name: string): number {
  const sources = [
    readFileSync(join(__dirname, "..", "styles", "globals.css"), "utf8"),
    readFileSync(createRequire(import.meta.url).resolve("tailwindcss/theme.css"), "utf8"),
  ];
  for (const css of sources) {
    const match = css.match(new RegExp(`--breakpoint-${name}:\\s*([\\d.]+)rem;`));
    if (match) return Number(match[1]) * 16;
  }
  throw new Error(`--breakpoint-${name} isn't declared`);
}

describe("BREAKPOINTS (UI-ISS-059: one source for JS and CSS)", () => {
  it("are the spec's widths", () => {
    expect(BREAKPOINTS).toEqual({ md: 768, lg: 1024, xl: 1280, wide: 1440 });
  });

  it("match the widths CSS's md:, lg:, xl: and wide: switch at", () => {
    for (const [name, px] of Object.entries(BREAKPOINTS)) expect(cssBreakpointPx(name), name).toBe(px);
  });

  it("give useMediaQuery its min-width queries", () => {
    expect(minWidth("md")).toBe("(min-width: 768px)");
    expect(minWidth("wide")).toBe("(min-width: 1440px)");
  });
});
