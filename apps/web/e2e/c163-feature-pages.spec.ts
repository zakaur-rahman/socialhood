import { expect, test } from "./support/fixtures";

/**
 * C-163 (feat): the three deeper feature pages and the internal links. Each page renders one h1 with no
 * page errors and no sideways scroll at 375, 768, 1440 and 1920; the "On this page" bar sticks under
 * the header and marks the section being read; the page marks up its own questions as FAQPage; the
 * audience pages are linked. The header's Pricing and FAQ (bar and phone menu) lead to /pricing and
 * /faq; the landing's features section links /features.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const PAGES = ["/features/ai-inbox", "/features/comment-intelligence", "/features/publishing"] as const;
const WIDTHS = [375, 768, 1440, 1920] as const;

test.describe("C-163 feature pages", () => {
  for (const path of PAGES) {
    test(`${path}: one h1, no errors, no sideways scroll, its own FAQPage`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
        const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(sideways, `${path} at ${width}`).toBeLessThanOrEqual(0);
      }
      const types = await page.locator('script[type="application/ld+json"]').evaluateAll((nodes) => nodes.map((node) => JSON.parse(node.textContent ?? "{}")["@type"]));
      expect(types).toContain("FAQPage");
      await expect(page.locator("#who-its-for").getByRole("link", { name: /for creators/ })).toHaveAttribute("href", "/for-creators");
      await expect(page.locator("#who-its-for").getByRole("link", { name: /for businesses/ })).toHaveAttribute("href", "/for-businesses");
      expect(errors).toEqual([]);
    });
  }

  test("the bar sticks under the header and marks the section being read", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/features/ai-inbox");
    const bar = page.locator(".fp-bar").getByRole("navigation", { name: "On this page" });
    await bar.getByRole("link", { name: "Plans and credits" }).click();
    await expect(page).toHaveURL(/#plans-and-credits$/);
    await expect(bar.locator('a[aria-current="location"]')).toHaveText("Plans and credits");
    const top = await page.locator(".fp-bar").evaluate((el) => el.getBoundingClientRect().top);
    expect(top).toBeGreaterThanOrEqual(0);
    expect(top).toBeLessThan(120);
    // The section's heading isn't hidden under the header and the bar.
    const heading = await page.locator("#plans-title").evaluate((el) => el.getBoundingClientRect().top);
    expect(heading).toBeGreaterThan(top);
  });

  test("the header's Pricing and FAQ lead to their pages, in the bar and the phone menu", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/features/publishing");
    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link", { name: "Pricing", exact: true })).toHaveAttribute("href", "/pricing");
    await expect(nav.getByRole("link", { name: "FAQ", exact: true })).toHaveAttribute("href", "/faq");
    await page.setViewportSize({ width: 375, height: 800 });
    await page.getByRole("button", { name: "Open menu" }).click();
    const menu = page.locator(`#${await page.getByRole("button", { name: "Close menu" }).getAttribute("aria-controls")}`);
    await expect(menu.getByRole("link", { name: "Pricing", exact: true })).toHaveAttribute("href", "/pricing");
    await expect(menu.getByRole("link", { name: "FAQ", exact: true })).toHaveAttribute("href", "/faq");
  });

  test("the landing's features section links every feature", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("section#features").getByRole("link", { name: "See every feature" })).toHaveAttribute("href", "/features");
  });
});
