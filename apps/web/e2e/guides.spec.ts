import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "./support/fixtures";

/**
 * C-153 guides, signed out: one h1, metadata, structured data, the feed and the sitemap, the
 * redirects left by the Hinglish page and guide (C-155), no sideways scroll at 375, 768 and
 * 1280 px. With GUIDES_SHOTS_DIR set, it also saves full-page screenshots there for a look.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const GUIDE = "/guides/comment-to-dm-automations";
const WIDTHS = [375, 768, 1280] as const;
const SHOTS_DIR = process.env.GUIDES_SHOTS_DIR;

async function jsonLd(page: import("@playwright/test").Page): Promise<Record<string, unknown>[]> {
  const blocks = await page.locator('script[type="application/ld+json"]').allTextContents();
  return blocks.map((text) => JSON.parse(text) as Record<string, unknown>);
}

test.describe("C-153 guides", () => {
  test("the index lists the guides newest first and links to each", async ({ page }) => {
    await page.goto("/guides");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await expect(page).toHaveTitle(/Guides for Instagram and WhatsApp sellers · Amplychat/);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/guides$/);
    await expect(page.locator('link[rel="alternate"][type="application/rss+xml"]')).toHaveAttribute("href", /\/guides\/rss\.xml$/);
    await expect(page.getByRole("article")).toHaveCount(3);
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

  test("a guide reads in two columns with its contents, anchors, question cards and related guides (C-159)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(GUIDE);
    const toc = page.getByRole("navigation", { name: "On this page" });
    await expect(toc).toBeVisible();
    const links = toc.getByRole("link");
    await expect(links).toHaveCount(8);
    await expect(links.last()).toHaveText("Common questions");
    // Every entry points at a heading on the page, and each body section links to itself.
    for (const href of await links.evaluateAll((els) => els.map((el) => el.getAttribute("href")))) {
      await expect(page.locator(`h2${href}`)).toHaveCount(1);
    }
    await expect(page.locator('[data-guide-body] h2 a[href^="#"]')).toHaveCount(7);
    // The side column sits beside the article, and stays in view while reading.
    const side = page.getByRole("complementary", { name: "About this guide" });
    const [article, aside] = await Promise.all([page.locator("[data-guide-body]").boundingBox(), side.boundingBox()]);
    expect(aside!.x).toBeGreaterThan(article!.x + article!.width);
    await toc.getByRole("link", { name: "Writing the messages" }).click();
    await expect(page).toHaveURL(/#writing-the-messages$/);
    await expect(toc.getByRole("link", { name: "Writing the messages" })).toHaveAttribute("aria-current", "location");
    await expect(side.getByRole("link", { name: /Start free/ })).toBeInViewport();
    // The questions are on the page as the FAQPage says.
    const data = await jsonLd(page);
    const faq = data.flatMap((block) => (block["@graph"] as Record<string, unknown>[] | undefined) ?? [block]).find((node) => node["@type"] === "FAQPage");
    for (const item of faq!.mainEntity as { name: string; acceptedAnswer: { text: string } }[]) {
      await expect(page.locator("dt", { hasText: item.name })).toBeVisible();
      await expect(page.locator("dd", { hasText: item.acceptedAnswer.text })).toHaveCount(1);
    }
    // Keep reading: the other guides as cards, then the night close.
    await expect(page.getByRole("region", { name: "Keep reading" }).getByRole("article")).toHaveCount(2);
    await expect(page.locator("section.night.close")).toHaveCount(1);
  });

  test("on a phone the contents fold into a disclosure above the body (C-159)", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(GUIDE);
    await expect(page.getByRole("complementary", { name: "About this guide" })).toBeHidden();
    const contents = page.locator("details.g-toc-m");
    await contents.locator("summary").click();
    await contents.getByRole("link", { name: "Choosing the keyword" }).click();
    await expect(page).toHaveURL(/#choosing-the-keyword$/);
  });

  test("an unknown guide is a 404", async ({ page }) => {
    const response = await page.goto("/guides/not-a-guide");
    expect(response?.status()).toBe(404);
  });

  test("the Hinglish page and guide are gone: their URLs move permanently, and nothing names a language alternate (C-155)", async ({ page, request }) => {
    for (const [from, to] of [
      ["/hi", "/"],
      ["/guides/replying-in-hinglish", "/guides"],
    ] as const) {
      const response = await request.get(from, { maxRedirects: 0 });
      expect(response.status(), from).toBe(308);
      expect(new URL(response.headers()["location"] ?? "", "http://x").pathname, from).toBe(to);
    }

    await page.goto("/");
    await expect(page.locator('link[rel="alternate"][hreflang]')).toHaveCount(0);
    const footer = page.getByRole("contentinfo");
    await expect(footer.getByRole("link", { name: "Guides" })).toHaveAttribute("href", "/guides");
    await expect(footer.getByRole("link", { name: /Hinglish/ })).toHaveCount(0);
  });

  test("the feed and the sitemap list the guides", async ({ request }) => {
    const feed = await request.get("/guides/rss.xml");
    expect(feed.ok()).toBe(true);
    expect(feed.headers()["content-type"]).toContain("application/rss+xml");
    expect((await feed.text()).match(/<item>/g)).toHaveLength(3);

    const sitemap = await (await request.get("/sitemap.xml")).text();
    for (const path of ["/guides</loc>", `${GUIDE}</loc>`]) expect(sitemap).toContain(path);
    expect(sitemap).not.toContain("/hi</loc>");
    expect(sitemap).not.toContain("hinglish");
    expect(sitemap).not.toContain("hreflang");
  });

  for (const path of ["/guides", GUIDE]) {
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
