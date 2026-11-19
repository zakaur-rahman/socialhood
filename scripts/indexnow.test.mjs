// node --test scripts/indexnow.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { changed, entries } from "./indexnow.mjs";

const sitemap = (...pages) =>
  `<?xml version="1.0"?><urlset>${pages
    .map(([url, mod]) => `<url>\n<loc>${url}</loc>${mod ? `\n<lastmod>${mod}</lastmod>` : ""}\n</url>`)
    .join("\n")}</urlset>`;

test("reads each page and its date", () => {
  const found = entries(sitemap(["https://amplychat.com/", "2026-11-14"], ["https://amplychat.com/pricing"]));
  assert.deepEqual([...found], [
    ["https://amplychat.com/", "2026-11-14"],
    ["https://amplychat.com/pricing", ""],
  ]);
});

test("sends added, changed and removed pages, not unchanged ones", () => {
  const before = entries(sitemap(["https://amplychat.com/a", "2026-11-01"], ["https://amplychat.com/b", "2026-11-01"], ["https://amplychat.com/gone", "2026-10-01"]));
  const after = entries(sitemap(["https://amplychat.com/a", "2026-11-01"], ["https://amplychat.com/b", "2026-11-18"], ["https://amplychat.com/new", "2026-11-18"]));
  assert.deepEqual(changed(before, after), ["https://amplychat.com/b", "https://amplychat.com/new", "https://amplychat.com/gone"]);
});

test("with no sitemap from before, every page is sent", () => {
  const after = entries(sitemap(["https://amplychat.com/", "2026-11-14"], ["https://amplychat.com/pricing", "2026-11-02"]));
  assert.deepEqual(changed(entries(""), after), ["https://amplychat.com/", "https://amplychat.com/pricing"]);
});
