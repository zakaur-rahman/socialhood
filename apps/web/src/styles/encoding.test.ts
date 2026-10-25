import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Every source file is UTF-8. Turbopack refuses a file with one stray byte ("failed to convert
 * rope into string"), and it happened once: a "§" saved by a Windows tool as the single byte A7.
 * This catches it in vitest and CI instead of in the dev server.
 */
const SRC = join(__dirname, "..");
const EXTENSIONS = /\.(ts|tsx|css|json|md)$/;

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "node_modules" ? [] : walk(path);
    return EXTENSIONS.test(name) ? [path] : [];
  });
}

describe("source encoding", () => {
  it("every source file under src/ is valid UTF-8", () => {
    const decoder = new TextDecoder("utf-8", { fatal: true });
    const broken = walk(SRC).filter((file) => {
      try {
        decoder.decode(readFileSync(file));
        return false;
      } catch {
        return true;
      }
    });
    expect(broken.map((file) => relative(SRC, file))).toEqual([]);
  });
});
