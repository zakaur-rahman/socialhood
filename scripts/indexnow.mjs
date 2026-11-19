// IndexNow (C-200): after a production deploy, tells Bing, Yandex and the other IndexNow search
// engines which public pages were added, changed or removed, by comparing the sitemap before and
// after the deploy (its dates are when each page's content changed). Google doesn't use IndexNow.
// It never fails a deploy: any problem is printed as a warning.
//
//   node scripts/indexnow.mjs <the sitemap saved before the deploy>
//
// A missing or empty "before" file sends every page (the first deploy with the key file).
// The key is the name of apps/web/public/<key>.txt, served at https://amplychat.com/<key>.txt,
// which is how the engines check we own the site (INDEXNOW_KEY overrides it).
import { readdirSync, readFileSync } from "node:fs";

const SITE = process.env.INDEXNOW_SITE ?? "https://amplychat.com";
const KEY = process.env.INDEXNOW_KEY ?? keyFile();
const ENDPOINT = "https://api.indexnow.org/indexnow";
const MAX_URLS = 10_000; // IndexNow's limit per request

/** The key: the name of the one 32-hex-digit .txt file in apps/web/public, or "". */
function keyFile() {
  try {
    const name = readdirSync(new URL("../apps/web/public/", import.meta.url)).find((f) => /^[0-9a-f]{32}\.txt$/.test(f));
    return name ? name.slice(0, -4) : "";
  } catch {
    return "";
  }
}

/** url → lastmod ("" when none), from a sitemap's XML. */
export function entries(xml) {
  const found = new Map();
  for (const [, body] of xml.matchAll(/<url>([\s\S]*?)<\/url>/g)) {
    const loc = body.match(/<loc>\s*([^<\s]+)\s*<\/loc>/)?.[1];
    if (loc) found.set(loc, body.match(/<lastmod>\s*([^<\s]+)\s*<\/lastmod>/)?.[1] ?? "");
  }
  return found;
}

/** Pages added or changed (another lastmod) in `after`, then pages removed from `before`. */
export function changed(before, after) {
  const touched = [...after].filter(([url, mod]) => before.get(url) !== mod).map(([url]) => url);
  return [...touched, ...[...before.keys()].filter((url) => !after.has(url))];
}

async function main() {
  const warn = (message) => console.log(`::warning::IndexNow: ${message}`);
  if (!/^[0-9a-f]{32}$/.test(KEY)) return warn("no key file in apps/web/public; nothing sent.");
  const keyLocation = `${SITE}/${KEY}.txt`;
  const live = await fetch(keyLocation);
  if (!live.ok || (await live.text()).trim() !== KEY) return warn(`${keyLocation} doesn't serve the key; nothing sent.`);

  let before = "";
  try {
    before = readFileSync(process.argv[2] ?? "", "utf8");
  } catch {
    // No sitemap from before the deploy: send every page.
  }
  const sitemap = await fetch(`${SITE}/sitemap.xml`);
  if (!sitemap.ok) return warn(`sitemap.xml answered ${sitemap.status}; nothing sent.`);
  const urlList = changed(entries(before), entries(await sitemap.text())).slice(0, MAX_URLS);
  if (urlList.length === 0) return console.log("IndexNow: no page changed.");

  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ host: new URL(SITE).host, key: KEY, keyLocation, urlList }),
  });
  // 200 and 202 (accepted, the key is checked later) are both fine.
  if (response.ok) console.log(`IndexNow: sent ${urlList.length} page(s), answer ${response.status}.`);
  else warn(`answered ${response.status} for ${urlList.length} page(s).`);
}

if (process.argv[1]?.endsWith("indexnow.mjs")) {
  main().catch((error) => console.log(`::warning::IndexNow: ${error.message}`));
}
