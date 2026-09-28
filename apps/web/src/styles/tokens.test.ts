import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { colorTokens, gradientUtilities } from "./tokens";

const css = readFileSync(join(__dirname, "globals.css"), "utf8");

function declared(name: string): string | undefined {
  const match = css.match(new RegExp(`--color-${name}:\\s*([^;]+);`));
  return match?.[1].trim();
}

describe("design tokens (§4.2, UX-TOK-01)", () => {
  it.each(colorTokens)("globals.css defines $name as $value", ({ name, value }) => {
    expect(declared(name)).toBe(value);
  });

  it.each(gradientUtilities)("defines the $name utility", ({ name, value }) => {
    expect(css).toContain(`@utility ${name} { background-image: ${value}; }`);
  });

  it("maps shadcn's semantic variables onto the tokens", () => {
    expect(css).toMatch(/--background:\s*var\(--color-canvas\)/);
    expect(css).toMatch(/--primary:\s*var\(--color-brand\)/);
    expect(css).toMatch(/--ring:\s*var\(--color-brand\)/);
  });

  it("keeps the WCAG fixes from UX-TOK-02", () => {
    expect(css).toContain("#4467E6"); // bubble gradient ends at 4.9:1, not #567FF8
    expect(declared("brand-fg")).toBe("#9DB5FF");
    expect(declared("fg-secondary")).toBe("#9B9CA0");
    expect(declared("danger-fill")).toBe("#C53030");
  });
});
