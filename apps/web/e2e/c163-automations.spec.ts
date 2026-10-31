import { expect, test } from "./support/fixtures";

/**
 * C-163 (auto): the automation and channel pages and their hub. Each renders one h1 with no page
 * errors and no sideways scroll at 375, 768 and 1440; a page's structured data is an Article with its
 * FAQPage and a three-level breadcrumb; the contents link to the sections; the hub links every page
 * and the footer links the hub; the features bento leads to comment-to-DM.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const PAGES = [
  "/automations",
  "/instagram/comment-to-dm",
  "/instagram/story-replies",
  "/instagram/dm-keywords",
  "/instagram/conversation-starters",
  "/whatsapp/auto-reply",
  "/website-chat",
] as const;
const WIDTHS = [375, 768, 1440] as const;

test.describe("C-163 automation pages", () => {
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

  test("a page: Article, FAQPage and breadcrumb; the contents jump to a section", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/instagram/comment-to-dm");
    const data = await page.locator('script[type="application/ld+json"]').allTextContents();
    const parsed = data.map((text) => JSON.parse(text) as Record<string, unknown>);
    const graph = parsed.find((item) => "@graph" in item)?.["@graph"] as { "@type": string }[];
    expect(graph.map((node) => node["@type"])).toEqual(["Article", "FAQPage"]);
    const crumbs = parsed.find((item) => item["@type"] === "BreadcrumbList") as { itemListElement: { name: string }[] };
    expect(crumbs.itemListElement.map((item) => item.name)).toEqual(["Home", "Automations", "Instagram comment to DM"]);
    const side = page.getByRole("complementary", { name: "About this page" });
    await side.getByRole("link", { name: "Plan limits and AI credits" }).click();
    await expect(page).toHaveURL(/#plan-limits-and-ai-credits$/);
    await expect(page.locator("#plan-limits-and-ai-credits")).toBeInViewport();
  });

  test("the hub links every page; the footer and the features bento lead into the set", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/automations");
    for (const path of PAGES.slice(1)) await expect(page.locator(`main a[href="${path}"]`).first()).toBeVisible();
    await expect(page.getByRole("contentinfo").getByRole("link", { name: "Automations" })).toHaveAttribute("href", "/automations");
    await page.goto("/features");
    await page.locator("#f-comments").getByRole("link").click();
    await expect(page).toHaveURL(/\/instagram\/comment-to-dm$/);
  });
});
