import { expect, test } from "./support/fixtures";

/**
 * The landing page (C-138), signed out: every feature illustration has content (they were empty
 * boxes once), the sections come in the planned order, nothing scrolls sideways on a phone, and
 * the page's layout shift stays under 0.1 (Google's "good") while it loads and is scrolled through.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const LIMIT = 0.1;
const VIEWPORTS = [
  { name: "phone", size: { width: 375, height: 800 } },
  { name: "tablet", size: { width: 768, height: 900 } },
  { name: "desktop", size: { width: 1280, height: 800 } },
  { name: "wide", size: { width: 1536, height: 900 } },
];

test.describe("landing page", () => {
  for (const { name, size } of VIEWPORTS) {
    test(`illustrations are filled, layout is stable and fits (${name})`, async ({ page }) => {
      await page.setViewportSize(size);
      await page.addInitScript(() => {
        const w = window as unknown as { __cls: number };
        w.__cls = 0;
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) {
            if (!entry.hadRecentInput) w.__cls += entry.value;
          }
        }).observe({ type: "layout-shift", buffered: true });
      });
      await page.goto("/");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

      // The pictures are in the markup before any scrolling.
      const boxes = page.locator("[data-illustration]");
      expect(await boxes.count()).toBeGreaterThanOrEqual(10);
      for (const box of await boxes.all()) {
        expect(((await box.textContent()) ?? "").trim().length).toBeGreaterThan(10);
      }

      // Scroll through the whole page, as a visitor would.
      const height = await page.evaluate(() => document.documentElement.scrollHeight);
      for (let y = 0; y < height; y += 400) {
        await page.evaluate((top) => window.scrollTo(0, top), y);
        await page.waitForTimeout(80);
      }
      await page.waitForTimeout(500);

      // Sections in order.
      const order = await page.$$eval("main > section", (sections) => sections.map((s) => s.id || s.getAttribute("aria-labelledby") || s.getAttribute("aria-label")));
      expect(order).toEqual([
        "hero-title",
        "inbox-shot-title",
        "integrations",
        "features",
        "how-it-works",
        "showcase-title",
        "languages-title",
        "The product in numbers",
        "pricing",
        "trust-title",
        "faq",
        "cta-title",
      ]);

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
      expect(cls, `layout shift on / at ${name}`).toBeLessThanOrEqual(LIMIT);
    });
  }
});
