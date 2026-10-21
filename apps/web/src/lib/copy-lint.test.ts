import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * UI-068's copy lint: one name per concept (UX_AUDIT §5), UK spelling (§6.2) and sentence case
 * (§6.1), checked across the app's source so an old variant can't come back. Each entry is a
 * user-visible string that was replaced, with what it became. Tests and this file are skipped.
 */
const BANNED: [RegExp, string][] = [
  [/["'>]\s*Train AI\b/, "Add answer"],
  [/["'>]\s*Teach AI\b/, "Add answer"],
  [/["'>]\s*Add to knowledge\b/, "Add answer"],
  [/["'>]\s*Add an FAQ\b/, "Add an answer"],
  [/["'>]\s*View thread\b/, "Open conversation (thread is for Ask)"],
  [/["'>]\s*Open chat\b/, "Open conversation"],
  [/Review & Send/, "Review and send"],
  [/["'>]\s*Canceled\b/, "Cancelled (UK spelling)"],
  [/["'>]\s*AI handled\b/, "Handled by AI"],
  [/["'>]\s*Summarize\b/, "Summarise (UK spelling)"],
  [/["'>]\s*Coming later\b/, "Coming soon"],
  [/["'>]\s*Chosen posts\b/, "Selected posts"],
  [/(Dismiss|Editing) suggestion\b/, "Dismiss draft / Editing AI draft"],
  [/["'>]\s*Open Inbox\b/, "Open inbox"],
  [/["'>]\s*AI Polish\b/, "AI polish"],
];

const SRC = join(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe("copy lint (UI-068)", () => {
  it("uses one name per concept, sentence case and UK spelling in what users read", () => {
    const hits: string[] = [];
    for (const file of sourceFiles(SRC)) {
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, index) => {
        if (/^\s*(\/\/|\/?\*)/.test(line)) return; // comments may name the old variants
        for (const [pattern, use] of BANNED) {
          if (pattern.test(line)) hits.push(`${relative(SRC, file)}:${index + 1}: use "${use}"`);
        }
      });
    }
    expect(hits).toEqual([]);
  });
});
