// Compares two runs of `pnpm shots:ui` (README.md in this folder): every PNG with the same name in
// both folders, pixel by pixel, in headless Chromium (no image library needed).
//
//   node scripts/ui-shots/compare.mjs <before-folder> <after-folder> [<out-folder>]
//
// Writes <out-folder> (default <after-folder>/diff): one diff image per changed screenshot (the
// "after" dimmed, changed pixels in magenta) and index.html with before, after and diff side by
// side, most-changed first. Prints the changed, unchanged, added and removed files. A pixel counts
// as changed when a colour channel moves by more than TOLERANCE (anti-aliasing stays quiet);
// screenshots of different heights are compared on the larger canvas, so the extra area counts.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, join, relative, resolve } from "node:path";

import { chromium } from "@playwright/test";

const TOLERANCE = 24;

const [beforeArg, afterArg, outArg] = process.argv.slice(2);
if (!beforeArg || !afterArg) {
  console.error("usage: node scripts/ui-shots/compare.mjs <before-folder> <after-folder> [<out-folder>]");
  process.exit(2);
}
const before = resolve(beforeArg);
const after = resolve(afterArg);
const out = resolve(outArg ?? join(after, "diff"));
for (const dir of [before, after]) {
  if (!existsSync(dir)) {
    console.error(`No such folder: ${dir}`);
    process.exit(2);
  }
}
mkdirSync(out, { recursive: true });

const pngs = (dir) => new Set(readdirSync(dir).filter((name) => name.endsWith(".png")));
const a = pngs(before);
const b = pngs(after);
const both = [...a].filter((name) => b.has(name)).sort();
const removed = [...a].filter((name) => !b.has(name)).sort();
const added = [...b].filter((name) => !a.has(name)).sort();

function compareInPage({ left, right, tolerance }) {
  const load = async (src) => {
    const image = new Image();
    image.src = src;
    await image.decode();
    return image;
  };
  return Promise.all([load(left), load(right)]).then(([one, two]) => {
    const width = Math.max(one.naturalWidth, two.naturalWidth);
    const height = Math.max(one.naturalHeight, two.naturalHeight);
    const pixels = (image) => {
      const canvas = new OffscreenCanvas(width, height);
      const context = canvas.getContext("2d");
      context.drawImage(image, 0, 0);
      return context.getImageData(0, 0, width, height).data;
    };
    const p = pixels(one);
    const q = pixels(two);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    const diff = context.createImageData(width, height);
    let changed = 0;
    for (let i = 0; i < p.length; i += 4) {
      const moved =
        Math.abs(p[i] - q[i]) > tolerance ||
        Math.abs(p[i + 1] - q[i + 1]) > tolerance ||
        Math.abs(p[i + 2] - q[i + 2]) > tolerance ||
        Math.abs(p[i + 3] - q[i + 3]) > tolerance;
      if (moved) {
        changed += 1;
        diff.data.set([255, 0, 200, 255], i);
      } else {
        const grey = Math.round((q[i] + q[i + 1] + q[i + 2]) / 3 / 4);
        diff.data.set([grey, grey, grey, 255], i);
      }
    }
    context.putImageData(diff, 0, 0);
    return {
      changed,
      total: width * height,
      before: [one.naturalWidth, one.naturalHeight],
      after: [two.naturalWidth, two.naturalHeight],
      diff: changed > 0 ? canvas.toDataURL("image/png") : null,
    };
  });
}

const browser = await chromium.launch();
const page = await browser.newPage();
const results = [];
for (const name of both) {
  const dataUrl = (dir) => `data:image/png;base64,${readFileSync(join(dir, name)).toString("base64")}`;
  const result = await page.evaluate(compareInPage, { left: dataUrl(before), right: dataUrl(after), tolerance: TOLERANCE });
  if (result.diff) {
    mkdirSync(join(out, "diff"), { recursive: true });
    writeFileSync(join(out, "diff", name), Buffer.from(result.diff.slice(result.diff.indexOf(",") + 1), "base64"));
  }
  results.push({ name, ...result, diff: Boolean(result.diff) });
}
await browser.close();

const changed = results.filter((r) => r.changed > 0).sort((x, y) => y.changed / y.total - x.changed / x.total);
const unchanged = results.filter((r) => r.changed === 0);
const percent = (r) => `${((100 * r.changed) / r.total).toFixed(2)}%`;
const size = (r) => (r.before.join("x") === r.after.join("x") ? r.after.join(" × ") : `${r.before.join(" × ")} → ${r.after.join(" × ")}`);
const rel = (dir, name) => relative(out, join(dir, name)).replaceAll("\\", "/");
const escape = (text) => text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const rows = changed
  .map(
    (r) => `<section><h2>${escape(r.name)} <small>${percent(r)} changed · ${size(r)}</small></h2>
<div class="row"><figure><figcaption>Before</figcaption><img src="${rel(before, r.name)}" alt=""></figure>
<figure><figcaption>After</figcaption><img src="${rel(after, r.name)}" alt=""></figure>
<figure><figcaption>Diff</figcaption><img src="${rel(join(out, "diff"), r.name)}" alt=""></figure></div></section>`,
  )
  .join("\n");
const list = (title, names) => (names.length ? `<h2>${title}</h2><p>${names.map(escape).join(", ")}</p>` : "");
writeFileSync(
  join(out, "index.html"),
  `<!doctype html><meta charset="utf-8"><title>UI shots: ${escape(basename(before))} vs ${escape(basename(after))}</title>
<style>body{background:#111;color:#eee;font:14px system-ui;margin:16px}h2{font-size:16px;margin:24px 0 8px}small{color:#aaa;font-weight:400}
.row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;align-items:start}figure{margin:0}figcaption{color:#aaa;margin-bottom:4px}img{width:100%;border:1px solid #333}</style>
<h1>${escape(before)} → ${escape(after)}</h1>
<p>${changed.length} changed, ${unchanged.length} unchanged, ${added.length} added, ${removed.length} removed (tolerance ${TOLERANCE} per channel).</p>
${rows}
${list("Unchanged", unchanged.map((r) => r.name))}${list("Added (after only)", added)}${list("Removed (before only)", removed)}`,
);

for (const r of changed) console.log(`changed    ${r.name}  ${percent(r)}  ${size(r)}`);
console.log(`\n${changed.length} changed, ${unchanged.length} unchanged, ${added.length} added, ${removed.length} removed`);
// A --grep run compared with a full one leaves many files on one side: list them only when few.
const names = (list) => (list.length <= 12 ? list.join(", ") : `${list.length} files (listed in index.html)`);
if (added.length) console.log(`added: ${names(added)}`);
if (removed.length) console.log(`removed: ${names(removed)}`);
console.log(`report: ${join(out, "index.html")}`);
