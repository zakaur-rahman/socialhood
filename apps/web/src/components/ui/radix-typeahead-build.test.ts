import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

import { beforeAll, describe, expect, it } from "vitest";

/**
 * Select and menu typeahead in the production build. Radix stores what was typed (for a second)
 * in a call its published build marks `@__PURE__`; Next's SWC minifier took the mark for the whole
 * call and dropped it, so the built app matched one letter at a time: "Asia/K" in the time-zone
 * Select landed on Africa/Abidjan, "Te" on English. `patches/` removes the mark (package.json
 * `pnpm.patchedDependencies`). This minifies the installed Radix builds with Next's own SWC and
 * checks the call is still there, so a Radix upgrade that loses the patch fails here: re-create the
 * patch for the new version, or drop it once Radix ships the call unmarked.
 */

type Swc = {
  loadBindings: () => Promise<unknown>;
  minify: (source: string, options: Record<string, unknown>) => Promise<{ code: string }>;
};

const fromApp = createRequire(import.meta.url);
const swc = fromApp("next/dist/build/swc") as Swc;
// The app depends on `radix-ui`, which brings the primitives; resolve them from there.
const fromRadix = createRequire(fromApp.resolve("radix-ui"));

/** The ES module build Next bundles for the browser. */
function esmBuild(name: string): string {
  return join(dirname(fromRadix.resolve(name)), "index.mjs");
}

// The search resets a second after the last key: `window.setTimeout(() => updateSearch(""), 1e3)`.
// Once minified, only that call stores the search, so it shows whether the store survived.
const STORES_THE_SEARCH = /setTimeout\(\(\)=>[\w$]+\(""\),1e3\)/;

beforeAll(async () => {
  await swc.loadBindings();
});

describe.each(["@radix-ui/react-select", "@radix-ui/react-menu"])("%s typeahead, minified by Next", (name) => {
  it("still stores what was typed", async () => {
    const source = readFileSync(esmBuild(name), "utf8");
    expect(source, `${name} no longer has Radix's updateSearch; check its typeahead and this test`).toMatch(
      /function updateSearch\(value\)/
    );
    const { code } = await swc.minify(source, { compress: true, mangle: true, module: true });
    expect(code, `${name}'s typeahead keeps only the last letter once minified; see patches/`).toMatch(STORES_THE_SEARCH);
  });
});
