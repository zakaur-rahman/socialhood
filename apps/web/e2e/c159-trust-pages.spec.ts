import { expect, test } from "./support/fixtures";

/**
 * C-159 (trust): the legal pages, /security, /safety, /changelog, /ai-info, /contact and the 404 in the
 * premium layout. Each renders one h1 with no page errors and no sideways scroll at 375, 768, 1440 and
 * 1920; the legal contents sit beside the text on a wide screen, open, and mark the section being read
 * (TocSpy); on a phone they fold into a disclosure; tables scroll inside their own box; no layout shift.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const PAGES = [
  "/privacy",
  "/terms",
  "/refunds",
  "/shipping",
  "/data-deletion",
  "/subprocessors",
  "/cookies",
  "/dpa",
  "/accessibility",
  "/security",
  "/safety",
  "/changelog",
  "/ai-info",
  "/contact",
  "/unsubscribe",
] as const;

const WIDTHS = [375, 768, 1440, 1920] as const;

test.describe("C-159 trust pages", () => {
  for (const path of PAGES) {
    test(`${path}: one h1, no errors, no sideways scroll`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
        const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(sideways, `${path} at ${width}`).toBeLessThanOrEqual(0);
      }
      expect(errors).toEqual([]);
    });
  }

  test("legal contents: open beside the text on a wide screen, the current section marked", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/privacy");
    const contents = page.getByRole("navigation", { name: "Contents" });
    await expect(contents.getByRole("link", { name: /How long we keep it/ })).toBeVisible();
    await page.evaluate(() => document.getElementById("retention")?.scrollIntoView());
    await expect(contents.locator('a[aria-current="location"]')).toHaveText(/How long we keep it/);
    // The contents stay in view while the text scrolls.
    const top = await contents.evaluate((nav) => nav.getBoundingClientRect().top);
    expect(top).toBeGreaterThanOrEqual(0);
    expect(top).toBeLessThan(200);
  });

  test("legal contents fold into a disclosure on a phone; tables scroll in their own box", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/privacy");
    const contents = page.getByRole("navigation", { name: "Contents" });
    const link = contents.getByRole("link", { name: /How long we keep it/ });
    await expect(link).toBeHidden();
    await contents.getByText("Contents").click();
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/#retention$/);

    // Two-column tables fit a phone; tables of three or more columns keep a readable width and
    // scroll inside their own box.
    const overflows = await page.$$eval(".overflow-x-auto", (boxes) =>
      boxes.filter((el) => (el.querySelector("tr")?.children.length ?? 0) >= 3).map((el) => el.scrollWidth - el.clientWidth),
    );
    expect(overflows.length).toBeGreaterThan(0);
    for (const overflow of overflows) expect(overflow).toBeGreaterThan(0);
    const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(sideways).toBeLessThanOrEqual(0);
  });

  test("no layout shift while a legal page and the changelog load and scroll", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    for (const path of ["/terms", "/changelog"]) {
      await page.goto(path);
      await page.evaluate(
        () =>
          new Promise<void>((resolve) => {
            const w = window as unknown as { __cls: number };
            w.__cls = 0;
            new PerformanceObserver((list) => {
              for (const entry of list.getEntries() as unknown as { value: number; hadRecentInput: boolean }[]) {
                if (!entry.hadRecentInput) w.__cls += entry.value;
              }
            }).observe({ type: "layout-shift", buffered: true });
            setTimeout(resolve, 1500);
          }),
      );
      await page.mouse.wheel(0, 2400);
      await page.waitForTimeout(600);
      const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
      expect(cls, path).toBeLessThan(0.1);
    }
  });

  test("the 404 links the main pages", async ({ page }) => {
    const response = await page.goto("/no-such-page-c159");
    expect(response?.status()).toBe(404);
    const places = page.getByRole("navigation", { name: "Popular pages" });
    await expect(places.getByRole("link")).toHaveCount(6);
    await places.getByRole("link", { name: "Common questions" }).click();
    await expect(page).toHaveURL(/\/faq$/);
  });
});
