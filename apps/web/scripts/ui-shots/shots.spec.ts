import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import type { Page, Route, TestInfo } from "@playwright/test";

import { expect, test as base } from "../../e2e/support/fixtures";
import { AXE_TAGS, AXE_WIDTHS, HEIGHT, PHONE_BELOW, TOUCH_BELOW, axeDir, metaDir, outDir, reducedMotion, widths } from "./options";
import { SCREENS, type Screen, type ShotContext } from "./screens";
import { seeded, type Seeded } from "./seed";

/**
 * Visual QA (UI-019 and every later UI task): every screen in screens.ts at every width, dark, at
 * 1x, with touch emulation below 1024 px; full page, except viewport-only screens (open overlays);
 * axe at 375 and 1280 px. One test per screen and width, titled <screen>-<width> like its file, so
 * --grep picks them. README.md in this folder explains running it and diffing two runs.
 */

const test = base.extend<object, { qa: Seeded }>({
  qa: [
    async ({ api }, provide) => {
      await provide(await seeded(api, join(outDir(), ".seed.json")));
    },
    // Seeding waits on the worker (analysis, the AI draft, the backfill): under a minute when
    // the worker is idle, longer behind other jobs.
    { scope: "worker", timeout: 480_000 },
  ],
});

/** Hidden in every shot: the Next.js dev indicator (when pointed at `next dev`). */
const SHOT_STYLE = "nextjs-portal { display: none !important; }";

// Remote pictures (sandbox posts, seeded uploads) as a neutral placeholder with a cross, so
// thumbnails keep their shape in the shots without reaching the network. The e2e fixtures answer
// them with a 1x1 pixel; routes registered later win.
const PLACEHOLDER =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">' +
  '<rect width="1080" height="1080" fill="#4b5262"/><path d="M0 0L1080 1080M1080 0L0 1080" stroke="#5f6678" stroke-width="8"/></svg>';
const REMOTE_IMAGES = /^https:\/\/(picsum\.photos|fastly\.picsum\.photos|res\.cloudinary\.com|[^/]+\.cdninstagram\.com|[^/]+\.fbcdn\.net)\//;

async function placeholders(page: Page) {
  const fulfill = (route: Route) => route.fulfill({ status: 200, contentType: "image/svg+xml", body: PLACEHOLDER });
  await page.context().route(REMOTE_IMAGES, fulfill);
  await page.context().route("**/_next/image?**", fulfill);
}

/**
 * A coarse pointer and no hover at the touch widths (375 and 768): the primitives size their touch
 * targets with `pointer-coarse:`, so a touch shot taken with a fine pointer shows desktop heights.
 *
 * - Touch emulation is forced again from a second CDP session before the page loads, on top of
 *   Playwright's `hasTouch`/`isMobile`. (`Emulation.setEmulatedMedia` ignores `pointer` and `hover`
 *   in Chromium; touch emulation sets them and leaves the colour scheme and reduced motion alone.)
 * - Full-page shots at these widths are stitched from viewport captures (`stitchedFullPage`):
 *   Chromium's beyond-viewport capture, which Playwright's `fullPage` uses, drops touch emulation,
 *   renders the page with `pointer: fine` and leaves it fine afterwards.
 * - `expectPointer` checks `matchMedia` before and after each shot.
 */
async function forceCoarsePointer(page: Page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
}

/**
 * A full-page screenshot built from viewport captures, so touch emulation holds. The page never
 * scrolls: the first tile is the viewport at the top, and each later tile moves `<body>` up (and
 * left) with a transform, so everything stays in its scroll-0 state, as Playwright's `fullPage`
 * draws it (sticky bars where they sit in the first screen, scroll-linked effects at rest, viewport
 * units at the real viewport). Fixed elements belong to the first screen, so later tiles hide them;
 * each tile adds only the area earlier tiles didn't cover. `<body>`'s style and the fixed elements
 * are restored afterwards, so axe and `after` see the page as before.
 */
async function stitchedFullPage(page: Page, path: string): Promise<Buffer> {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("stitchedFullPage needs a viewport");
  const size = await page.evaluate(() => {
    window.scrollTo({ left: 0, top: 0, behavior: "instant" });
    for (const el of Array.from(document.body.querySelectorAll<HTMLElement>("*"))) {
      if (getComputedStyle(el).position === "fixed") el.setAttribute("data-ui-shots-fixed", "");
    }
    document.body.setAttribute("data-ui-shots-style", document.body.getAttribute("style") ?? "");
    const doc = document.documentElement;
    return {
      width: Math.max(doc.scrollWidth, document.body.scrollWidth),
      height: Math.max(doc.scrollHeight, document.body.scrollHeight),
    };
  });
  const tiles: { x: number; y: number; left: number; top: number; png: string }[] = [];
  const starts = (total: number, step: number) => {
    const list: number[] = [];
    for (let at = 0; at < total; at += step) list.push(Math.min(at, Math.max(0, total - step)));
    return [...new Set(list)];
  };
  let coveredY = 0;
  for (const y of starts(size.height, viewport.height)) {
    let coveredX = 0;
    for (const x of starts(size.width, viewport.width)) {
      await page.evaluate(
        ({ x, y }) => {
          const shifted = x !== 0 || y !== 0;
          if (shifted) document.body.style.setProperty("transform", `translate(${-x}px, ${-y}px)`, "important");
          else document.body.style.removeProperty("transform");
          for (const el of Array.from(document.querySelectorAll<HTMLElement>("[data-ui-shots-fixed]"))) {
            if (shifted) el.style.setProperty("visibility", "hidden", "important");
            else el.style.removeProperty("visibility");
          }
          return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        },
        { x, y },
      );
      // Pictures moved into view (lazy ones) get a moment to arrive.
      await page
        .waitForFunction(
          () =>
            Array.from(document.images).every((img) => {
              const r = img.getBoundingClientRect();
              return img.complete || r.bottom < 0 || r.top > innerHeight;
            }),
          undefined,
          { timeout: 5_000 },
        )
        .catch(() => undefined);
      const png = await page.screenshot({ animations: "disabled", caret: "hide", style: SHOT_STYLE });
      tiles.push({ x, y, left: coveredX, top: coveredY, png: png.toString("base64") });
      coveredX = x + viewport.width;
    }
    coveredY = y + viewport.height;
  }
  await page.evaluate(() => {
    const style = document.body.getAttribute("data-ui-shots-style");
    if (style) document.body.setAttribute("style", style);
    else document.body.removeAttribute("style");
    document.body.removeAttribute("data-ui-shots-style");
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("[data-ui-shots-fixed]"))) {
      el.style.removeProperty("visibility");
      el.removeAttribute("data-ui-shots-fixed");
    }
  });

  // Composed in a blank page of the same browser: each tile draws only what earlier tiles didn't.
  const composer = await page.context().browser()!.newPage();
  try {
    const base64 = await composer.evaluate(
      async ({ size, tiles }) => {
        const canvas = new OffscreenCanvas(size.width, size.height);
        const context = canvas.getContext("2d")!;
        for (const tile of tiles) {
          const image = new Image();
          image.src = `data:image/png;base64,${tile.png}`;
          await image.decode();
          const sx = tile.left - tile.x;
          const sy = tile.top - tile.y;
          const w = Math.min(image.naturalWidth - sx, size.width - tile.left);
          const h = Math.min(image.naturalHeight - sy, size.height - tile.top);
          if (w > 0 && h > 0) context.drawImage(image, sx, sy, w, h, tile.left, tile.top, w, h);
        }
        const blob = await canvas.convertToBlob({ type: "image/png" });
        const bytes = new Uint8Array(await blob.arrayBuffer());
        let binary = "";
        for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        return btoa(binary);
      },
      { size, tiles },
    );
    const png = Buffer.from(base64, "base64");
    writeFileSync(path, png);
    return png;
  } finally {
    await composer.close();
  }
}

async function expectPointer(page: Page, touch: boolean): Promise<"coarse" | "fine"> {
  const media = await page.evaluate(() => ({
    coarse: matchMedia("(pointer: coarse)").matches,
    anyCoarse: matchMedia("(any-pointer: coarse)").matches,
    noHover: matchMedia("(hover: none)").matches,
  }));
  expect(media, touch ? "a coarse pointer without hover at a touch width" : "a fine pointer with hover").toEqual({
    coarse: touch,
    anyCoarse: touch,
    noHover: touch,
  });
  return media.coarse ? "coarse" : "fine";
}

/** Loading states over, fonts and pictures in, finite animations done. Warns instead of failing. */
async function settle(page: Page, testInfo: TestInfo) {
  const soft = async (what: string, check: () => Promise<unknown>) => {
    try {
      await check();
    } catch {
      testInfo.annotations.push({ type: "warning", description: `${what} after waiting` });
      console.warn(`[ui-shots] ${testInfo.title}: ${what} after waiting`);
    }
  };
  await soft("still loading (aria-busy)", () => expect(page.locator('[aria-busy="true"]:visible')).toHaveCount(0, { timeout: 20_000 }));
  await soft("a skeleton still shown", () => expect(page.locator('[data-slot="skeleton"]:visible')).toHaveCount(0, { timeout: 10_000 }));
  // Clerk's script draws the account button (and the sign-in form) once it has loaded.
  await soft("Clerk still loading", () =>
    page.waitForFunction(() => (window as unknown as { Clerk?: { loaded?: boolean } }).Clerk?.loaded === true, undefined, { timeout: 15_000 }),
  );
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  await soft("a picture still loading", () =>
    page.waitForFunction(() => Array.from(document.images).every((img) => img.complete || img.loading === "lazy"), undefined, { timeout: 10_000 }),
  );
  await soft("an animation still running", () =>
    page.waitForFunction(
      () => document.getAnimations().every((a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity),
      undefined,
      { timeout: 5_000 },
    ),
  );
}

type AxeEntry = {
  screen: string;
  width: number;
  url: string;
  at: string;
  reducedMotion: boolean;
  violations: { id: string; impact: string | null; help: string; nodes: number; targets: string[]; html: string[] }[];
  /** What axe couldn't decide ("needs review"): colour contrast over images, gradients or overlaps. */
  incomplete: { id: string; nodes: number; reasons: Record<string, number> }[];
};

async function runAxe(page: Page, screen: Screen, width: number) {
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  const entry: AxeEntry = {
    screen: screen.name,
    width,
    url: new URL(page.url()).pathname,
    at: new Date().toISOString(),
    reducedMotion: reducedMotion() === "reduce",
    incomplete: results.incomplete.map((v) => {
      // Why axe couldn't decide, e.g. bgImage, bgGradient, bgOverlap, pseudoContent.
      const reasons: Record<string, number> = {};
      for (const node of v.nodes) {
        const data = [...node.any, ...node.all, ...node.none].find((check) => check.data)?.data as { messageKey?: string } | undefined;
        const key = data?.messageKey ?? "other";
        reasons[key] = (reasons[key] ?? 0) + 1;
      }
      return { id: v.id, nodes: v.nodes.length, reasons };
    }),
    violations: results.violations.map((v) => ({
      id: v.id,
      impact: v.impact ?? null,
      help: v.help,
      nodes: v.nodes.length,
      // A target is a CSS selector; one inside a frame or shadow root is a list of them.
      targets: v.nodes.map((node) => node.target.map((part) => (Array.isArray(part) ? part.join(" >>> ") : part)).join(" | ")),
      // The element's opening tag, to recognise it when the selector is a generated id.
      html: v.nodes.map((node) => node.html.replace(/\s+/g, " ").slice(0, 200)),
    })),
  };
  mkdirSync(axeDir(), { recursive: true });
  writeFileSync(join(axeDir(), `${screen.name}-${width}.json`), JSON.stringify(entry, null, 2));
}

async function capture(screen: Screen, ctx: ShotContext, testInfo: TestInfo) {
  const { page, width } = ctx;
  const touch = width < TOUCH_BELOW;
  await placeholders(page);
  if (touch) await forceCoarsePointer(page);
  try {
    await screen.open(ctx);
    await settle(page, testInfo);
    const pointer = await expectPointer(page, touch);
    const file = `${screen.name}-${width}.png`;
    const png =
      touch && !screen.viewportOnly
        ? await stitchedFullPage(page, join(outDir(), file))
        : await page.screenshot({
            path: join(outDir(), file),
            fullPage: !screen.viewportOnly,
            animations: "disabled",
            caret: "hide",
            style: SHOT_STYLE,
          });
    // The capture mustn't have changed the pointer (axe and `after` run next).
    await expectPointer(page, touch);
    mkdirSync(metaDir(), { recursive: true });
    writeFileSync(
      join(metaDir(), `${screen.name}-${width}.json`),
      JSON.stringify({
        screen: screen.name,
        what: screen.what,
        width,
        file,
        url: new URL(page.url()).pathname,
        fullPage: !screen.viewportOnly,
        touch,
        pointer,
        reducedMotion: reducedMotion() === "reduce",
        bytes: png.length,
        warnings: testInfo.annotations.filter((a) => a.type === "warning").map((a) => a.description),
        at: new Date().toISOString(),
      }),
    );
    if (AXE_WIDTHS.includes(width)) await runAxe(page, screen, width);
  } catch (error) {
    // Undo what open may have changed, without hiding why the shot failed.
    await screen.after?.(ctx).catch((cleanup) => console.warn(`[ui-shots] ${screen.name}: cleanup failed too: ${String(cleanup).split("\n")[0]}`));
    throw error;
  }
  await screen.after?.(ctx);
}

for (const width of widths()) {
  const touch = width < TOUCH_BELOW;
  const phone = width < PHONE_BELOW;

  test.describe(`${width} px`, () => {
    test.use({
      viewport: { width, height: HEIGHT[width] ?? Math.round(width * 0.625) },
      deviceScaleFactor: 1,
      isMobile: touch,
      hasTouch: touch,
    });

    for (const screen of SCREENS) {
      if (screen.phoneOnly && !phone) continue;
      const title = `${screen.name}-${width}`;

      if (screen.signedOut) {
        test.describe(() => {
          test.use({ storageState: { cookies: [], origins: [] } });
          test(title, async ({ page }, testInfo) => {
            await capture(screen, { page, width, phone }, testInfo);
          });
        });
        continue;
      }

      test(title, async ({ page, qa }, testInfo) => {
        test.skip(Boolean(screen.needsBanner && !qa.banner), "the sandbox didn't mark the account needs_reconnect");
        await capture(screen, { page, width, phone, qa }, testInfo);
      });
    }
  });
}
