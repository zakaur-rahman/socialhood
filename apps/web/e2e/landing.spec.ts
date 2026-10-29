import { expect, test } from "./support/fixtures";

/**
 * The landing page (C-155, C-157), signed out: the scenes have content before any script, they come
 * to life once it loads (the hero sorts once and holds, How it works is live, the mode switch works,
 * the keyword field changes the automation), the sections come in the planned order, nothing scrolls
 * sideways, nothing loops without a pause control, and the page's layout shift stays under 0.1
 * (Google's "good") while it loads and is scrolled through.
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
      await expect(page.locator("[data-stage] .note .tag").first()).toHaveText("Needs you");
      await expect(page.locator("[data-kb] .line")).not.toHaveCount(0);
      await expect(page.locator("[data-comments] .cmt")).not.toHaveCount(0);
      // C-157: no scroll-scrubbed hero; it is one screen, and the next section starts right under it.
      await expect(page.locator("[data-hero-scrub]")).toHaveCount(0);
      // The motion script arrives after load and takes the scenes over; the hero's one sort ends within
      // about a second and leaves nothing running there.
      await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
      await expect
        .poll(() => page.evaluate(() => document.getAnimations().filter((a) => (a.effect as KeyframeEffect | null)?.target?.closest?.("[data-notes]")).length), { timeout: 5_000 })
        .toBe(0);

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

      // Sections in order (C-157): a night band every two or three sections, Security early, the
      // connections inside Features, the setup steps as the bridge into Pricing.
      const order = await page.$$eval("main > section", (sections) => sections.map((s) => s.id || s.getAttribute("aria-labelledby") || s.getAttribute("aria-label")));
      expect(order).toEqual([
        "hero-title",
        "The product in numbers",
        "how-it-works",
        "automations",
        "modes",
        "security",
        "who-its-for",
        "features",
        "setup",
        "pricing",
        "faq",
        "cta-title",
      ]);
      await expect(page.locator("section#features #integrations")).toHaveCount(1);
      // The FAQ shows 6 to 8 questions and links to the rest.
      const questions = await page.locator("section#faq details").count();
      expect(questions).toBeGreaterThanOrEqual(6);
      expect(questions).toBeLessThanOrEqual(8);
      await expect(page.locator("section#faq").getByRole("link", { name: "See all questions" })).toHaveAttribute("href", "/faq");

      // WCAG 2.2.2: nothing loops forever. The closer's inbox is still, and any infinite CSS animation
      // left on the page sits under a pause control.
      await expect(page.locator(".close .falling")).toHaveCount(0);
      const loose = await page.evaluate(() =>
        document
          .getAnimations()
          .filter((a) => a.playState === "running" && a.effect?.getComputedTiming().iterations === Infinity)
          .filter((a) => !((a.effect as KeyframeEffect | null)?.target as Element | null)?.closest("[data-motion-scope]")).length,
      );
      expect(loose).toBe(0);

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
      expect(cls, `layout shift on / at ${name}`).toBeLessThanOrEqual(LIMIT);
    });
  }

  test("the comment scene has a pause control that stops it, and How it works pins on a wide screen (C-157)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
    // How it works: the heading is inside the pinned frame.
    await expect(page.locator("[data-decide-sticky] h2")).toHaveText("AI replies from your own knowledge");
    expect(await page.locator("[data-decide-sticky]").evaluate((el) => getComputedStyle(el).position)).toBe("sticky");
    // Wide screens scrub it with the scroll, so it has no pause control of its own.
    await expect(page.locator("section#how-it-works [data-motion-toggle]")).toBeHidden();

    const automations = page.locator("section#automations");
    await automations.scrollIntoViewIfNeeded();
    const toggle = automations.getByRole("button", { name: "Pause the example" });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await expect(automations).toHaveAttribute("data-motion-paused", "");
    const count = await automations.locator("[data-comments] .cmt").allTextContents();
    await page.waitForTimeout(2_500);
    expect(await automations.locator("[data-comments] .cmt").allTextContents()).toEqual(count);
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  test("on a phone How it works plays once by itself, with a pause control", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/");
    await expect(page.locator("[data-decide][data-live]")).toHaveCount(1, { timeout: 15_000 });
    const how = page.locator("section#how-it-works");
    await how.locator("[data-kb]").scrollIntoViewIfNeeded();
    const toggle = how.getByRole("button", { name: "Pause the example" });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(how).toHaveAttribute("data-motion-paused", "");
  });
});

test.describe("all questions page", () => {
  test("/faq lists every question, the landing ones included, with matching FAQPage JSON-LD", async ({ page }) => {
    await page.goto("/faq");
    await expect(page.getByRole("heading", { level: 1, name: "Common questions" })).toBeVisible();
    const questions = await page.locator("main details summary h3").allTextContents();
    expect(questions.length).toBeGreaterThan(8);
    const data = await page.$$eval('script[type="application/ld+json"]', (scripts) => scripts.map((s) => JSON.parse(s.textContent ?? "null")));
    const faq = data.find((node) => node["@type"] === "FAQPage");
    expect(faq.mainEntity.map((entity: { name: string }) => entity.name)).toEqual(questions);
    expect(data.some((node) => node["@type"] === "BreadcrumbList")).toBe(true);
    // The first question opens.
    await page.locator("main details summary").first().click();
    await expect(page.locator("main details").first()).toHaveAttribute("open", "");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
