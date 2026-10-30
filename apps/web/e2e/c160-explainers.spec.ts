import { expect, test } from "./support/fixtures";

/**
 * C-160: /how-it-works and /features. Each renders one h1 with no page errors and no sideways scroll at
 * 375, 768, 1440 and 1920; the step tracker stays in view beside the stages on a wide screen and marks
 * the stage being read (toc-spy); a scene that starts off screen plays once as it arrives; the header's
 * Features and How it works links (bar and phone menu) and the footer's lead to the new pages; the
 * landing keeps its #features and #how-it-works anchors for its own links.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const PAGES = ["/how-it-works", "/features"] as const;
const WIDTHS = [375, 768, 1440, 1920] as const;

test.describe("C-160 explainer pages", () => {
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

  test("the step tracker stays beside the stages and marks the current one", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/how-it-works");
    const tracker = page.getByRole("navigation", { name: "The steps" });
    await expect(tracker.getByRole("link")).toHaveCount(8);
    await page.evaluate(() => document.getElementById("handoff")?.scrollIntoView());
    await expect(tracker.locator('a[aria-current="location"]')).toHaveText(/Hand-off and gaps/);
    const top = await tracker.evaluate((nav) => nav.getBoundingClientRect().top);
    expect(top).toBeGreaterThanOrEqual(0);
    expect(top).toBeLessThan(200);
    // A tracker link jumps to its stage and marks it.
    await tracker.getByRole("link", { name: /Add your knowledge/ }).click();
    await expect(tracker.locator('a[aria-current="location"]')).toHaveText(/Add your knowledge/);
  });

  test("the tracker is hidden on a phone, where the stages read as one column", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 820 });
    await page.goto("/how-it-works");
    await expect(page.getByRole("navigation", { name: "The steps" })).toBeHidden();
    await expect(page.locator("ol.xp-stages > li")).toHaveCount(8);
  });

  test("a scene that starts off screen plays once as it arrives; the mode switch works", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/how-it-works");
    const scene = page.locator("#results [data-xv]");
    await expect(scene).toHaveAttribute("data-xv", "armed");
    await page.evaluate(() => document.getElementById("results")?.scrollIntoView());
    await expect(scene).toHaveAttribute("data-xv", "in");
    await page.locator("#replies [data-mode='auto']").click();
    await expect(page.locator("#replies [data-mode-desc]")).toContainText("With Auto mode (Pro)");
  });

  test("features: the bento cells link to their pages and details", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/features");
    await expect(page.locator("ul.bento > li")).toHaveCount(15);
    await page.locator("#f-ask").getByRole("link").click();
    await expect(page).toHaveURL(/#d-ask$/);
    const nav = page.getByRole("navigation", { name: "Feature groups" });
    await expect(nav.locator('a[aria-current="location"]')).toHaveText(/Ask Amplychat/);
    await page.locator("#f-inbox").getByRole("link").click();
    await expect(page).toHaveURL(/\/features\/ai-inbox$/);
  });

  test("the header and footer lead to the new pages; the landing keeps its anchors", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    const main = page.getByRole("navigation", { name: "Main" });
    await expect(main.getByRole("link", { name: "Features" })).toHaveAttribute("href", "/features");
    await expect(main.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
    await expect(page.locator("section#features")).toHaveCount(1);
    await expect(page.locator("section#how-it-works")).toHaveCount(1);
    await expect(page.locator("section.hero").getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "#how-it-works");
    const footer = page.getByRole("contentinfo");
    await expect(footer.getByRole("link", { name: "Features" })).toHaveAttribute("href", "/features");
    await expect(footer.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
    await main.getByRole("link", { name: "How it works" }).click();
    await expect(page).toHaveURL(/\/how-it-works$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("From first message to reply");

    await page.setViewportSize({ width: 375, height: 820 });
    await page.getByRole("button", { name: "Open menu" }).click();
    await page.getByRole("navigation", { name: "Menu" }).getByRole("link", { name: "Features" }).click();
    await expect(page).toHaveURL(/\/features$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Everything your customer conversations need");
  });
});
