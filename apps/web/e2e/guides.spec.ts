import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "./support/fixtures";

/**
 * C-153 guides and the Hinglish page, signed out: one h1, metadata, structured data, hreflang,
 * the feed and the sitemap, no sideways scroll at 375, 768 and 1280 px. With GUIDES_SHOTS_DIR set,
 * it also saves full-page screenshots there for a look.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const GUIDE = "/guides/comment-to-dm-automations";
const WIDTHS = [375, 768, 1280] as const;
const SHOTS_DIR = process.env.GUIDES_SHOTS_DIR;

async function jsonLd(page: import("@playwright/test").Page): Promise<Record<string, unknown>[]> {
  const blocks = await page.locator('script[type="application/ld+json"]').allTextContents();
  return blocks.map((text) => JSON.parse(text) as Record<string, unknown>);
}

test.describe("C-153 guides and the Hinglish page", () => {
  test("the index lists the guides newest first and links to each", async ({ page }) => {
    await page.goto("/guides");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page).toHaveTitle(/Guides for Instagram and WhatsApp sellers · Amplychat/);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/guides$/);
    await expect(page.locator('link[rel="alternate"][type="application/rss+xml"]')).toHaveAttribute("href", /\/guides\/rss\.xml$/);
    await expect(page.getByRole("article")).toHaveCount(4);
    await page.getByRole("link", { name: /Comment-to-DM automations/ }).click();
    await expect(page).toHaveURL(new RegExp(`${GUIDE}$`));
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Comment-to-DM automations");
  });

  test("a guide has its byline, Article and breadcrumb data, and links back", async ({ page }) => {
    await page.goto(GUIDE);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page.getByText(/By Amplychat team/)).toBeVisible();
    await expect(page.locator('meta[property="og:type"]')).toHaveAttribute("content", "article");
    await expect(page.locator('meta[property="article:published_time"]')).toHaveAttribute("content", /^\d{4}-\d{2}-\d{2}/);
    const data = await jsonLd(page);
    const graph = data.flatMap((block) => (block["@graph"] as Record<string, unknown>[] | undefined) ?? [block]);
    expect(graph.find((node) => node["@type"] === "Article")).toMatchObject({ datePublished: expect.any(String), dateModified: expect.any(String) });
    expect(graph.find((node) => node["@type"] === "FAQPage")).toBeTruthy();
    expect(graph.find((node) => node["@type"] === "BreadcrumbList")?.itemListElement).toHaveLength(3);
    await page.getByRole("link", { name: "All guides" }).click();
    await expect(page).toHaveURL(/\/guides$/);
  });

  test("an unknown guide is a 404", async ({ page }) => {
    const response = await page.goto("/guides/not-a-guide");
    expect(response?.status()).toBe(404);
  });

  test("the Hinglish page and the landing page name each other", async ({ page }) => {
    await page.goto("/hi");
    await expect(page.locator("main")).toHaveAttribute("lang", "hi-Latn");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/hi$/);
    await expect(page.locator('link[rel="alternate"][hreflang="en"]')).toHaveAttribute("href", /^https?:\/\/[^/]+\/?$/);
    await expect(page.locator('link[rel="alternate"][hreflang="hi"]')).toHaveAttribute("href", /\/hi$/);

    await page.goto("/");
    await expect(page.locator('link[rel="alternate"][hreflang="hi"]')).toHaveAttribute("href", /\/hi$/);
    await expect(page.locator('link[rel="alternate"][hreflang="x-default"]')).toHaveAttribute("href", /^https?:\/\/[^/]+\/?$/);
    const footer = page.getByRole("contentinfo");
    await expect(footer.getByRole("link", { name: "Guides" })).toHaveAttribute("href", "/guides");
    await expect(footer.getByRole("link", { name: "Amplychat Hinglish mein" })).toHaveAttribute("lang", "hi-Latn");
  });

  test("the feed and the sitemap list the guides", async ({ request }) => {
    const feed = await request.get("/guides/rss.xml");
    expect(feed.ok()).toBe(true);
    expect(feed.headers()["content-type"]).toContain("application/rss+xml");
    expect((await feed.text()).match(/<item>/g)).toHaveLength(4);

    const sitemap = await (await request.get("/sitemap.xml")).text();
    for (const path of ["/guides</loc>", "/hi</loc>", `${GUIDE}</loc>`]) expect(sitemap).toContain(path);
    expect(sitemap).toContain('hreflang="hi"');
  });

  for (const path of ["/guides", GUIDE, "/hi"]) {
    test(`${path} fits 375, 768 and 1280 px`, async ({ page }) => {
      // The fixtures answer optimised images with a 1 px stand-in; screenshots need the real ones.
      if (SHOTS_DIR) await page.context().unroute("**/_next/image?**");
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `${path} at ${width}`).toBeLessThanOrEqual(0);
        for (const image of await page.locator("main img").all()) await expect(image).toHaveAttribute("alt", /.+/);
        if (SHOTS_DIR && width !== 768) {
          // Wait until every image has loaded before the screenshot.
          await page.waitForFunction(() => [...document.images].every((image) => image.complete && image.naturalWidth > 0));
          mkdirSync(SHOTS_DIR, { recursive: true });
          const name = `${path.replace(/^\//, "").replace(/\//g, "_") || "home"}-${width}.png`;
          await page.screenshot({ path: join(SHOTS_DIR, name), fullPage: true });
        }
      }
    });
  }
});
