import { expect, test } from "./support/fixtures";

/**
 * The landing page (C-155), signed out: the scenes have content before any script, they come to
 * life once it loads (the hero's notes move, the mode switch works, the keyword field changes the
 * automation), the sections come in the planned order, nothing scrolls sideways, and the page's
 * layout shift stays under 0.1 (Google's "good") while it loads and is scrolled through.
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
    test(`scenes are filled and live, layout is stable and fits (${name})`, async ({ page }) => {
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

      // The scenes are in the markup before any scrolling: the sorted inbox, the knowledge, the comments.
      await expect(page.locator("[data-stage] .note")).toHaveCount(8);
      await expect(page.locator("[data-kb] .line")).not.toHaveCount(0);
      await expect(page.locator("[data-comments] .cmt")).not.toHaveCount(0);
      // The motion script arrives after load and takes the scenes over.
      await expect(page.locator("[data-hero-scrub][data-live]")).toHaveCount(1, { timeout: 15_000 });

      // The mode switch and the keyword field work.
      const modes = page.locator("section#modes");
      await modes.getByRole("button", { name: /Auto/ }).click();
      await expect(modes.getByRole("button", { name: /Auto/ })).toHaveAttribute("aria-pressed", "true");
      await expect(modes.getByText("Sent by the AI").first()).toBeVisible();
      const keyword = page.getByRole("textbox", { name: "The keyword is yours" });
      await keyword.fill("guide");
      await expect(keyword).toHaveValue("GUIDE");
      await expect(page.locator("[data-kw-show]")).toHaveText("GUIDE");

      // Scroll through the whole page, as a visitor would.
      const height = await page.evaluate(() => document.documentElement.scrollHeight);
      for (let y = 0; y < height; y += 400) {
        await page.evaluate((top) => window.scrollTo(0, top), y);
        await page.waitForTimeout(80);
      }
      await page.waitForTimeout(500);

      // LP-1.1 (C-157): the AI draft keeps a transparent, block-level text box while it writes, so it
      // stays readable on the dark card (the DM's typing dots once shared its class).
      const draft = await page.locator(".ddraft-t").evaluate((el) => {
        const style = getComputedStyle(el);
        return { background: style.backgroundColor, display: style.display };
      });
      expect(draft).toEqual({ background: "rgba(0, 0, 0, 0)", display: "block" });

      // Sections in order.
      const order = await page.$$eval("main > section", (sections) => sections.map((s) => s.id || s.getAttribute("aria-labelledby") || s.getAttribute("aria-label")));
      expect(order).toEqual([
        "hero-title",
        "The product in numbers",
        "how-it-works",
        "automations",
        "modes",
        "features",
        "integrations",
        "security",
        "pricing",
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
