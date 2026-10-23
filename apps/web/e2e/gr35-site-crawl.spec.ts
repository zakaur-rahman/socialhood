import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

import { expect, test } from "./support/fixtures";

/**
 * GR-35 A website crawled into knowledge, on a local fixture site (a Node HTTP server; the e2e
 * stack sets CRAWL_ALLOW_PRIVATE so the API may read it). Add the site on the Knowledge page, watch
 * it read, open its pages, remove one, exclude a path, and crawl it again (the removed and the
 * excluded pages are not asked for). Checked at 375 px too.
 */
type Site = { server: Server; url: string; hits: Map<string, number>; pages: Map<string, string> };

const article = (title: string, topic: string, links: string[] = []) =>
  `<html><head><title>${title}</title></head><body><article><h1>${title}</h1>` +
  `<p>${topic}. Our team in Pune answers questions about this every day of the week, and we keep this page up to date.</p>` +
  `<p>If anything is unclear, message us and we will explain it in plain words, whenever you ask.</p></article>` +
  `<nav>${links.map((href) => `<a href="${href}">${href}</a>`).join(" ")}</nav></body></html>`;

async function startSite(): Promise<Site> {
  const hits = new Map<string, number>();
  const pages = new Map<string, string>([
    ["/", article("Maple Bakery", "Fresh cakes and bread", ["/shipping", "/returns", "/blog/first", "/private/secret"])],
    ["/shipping", article("Shipping policy", "Shipping to the UAE and India")],
    ["/returns", article("Returns", "Returns and refunds for cakes")],
    ["/blog/first", article("First post", "Our first blog post")],
    ["/private/secret", article("Secret", "Not for crawlers")],
  ]);
  const server = createServer((req, res) => {
    const path = (req.url ?? "/").split("?")[0];
    hits.set(path, (hits.get(path) ?? 0) + 1);
    if (path === "/robots.txt") {
      res.setHeader("content-type", "text/plain");
      res.end("User-agent: *\nDisallow: /private\n");
      return;
    }
    const body = pages.get(path);
    if (!body) {
      res.statusCode = 404;
      res.end("not found");
      return;
    }
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.end(body);
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return { server, url: `http://127.0.0.1:${port}/`, hits, pages };
}

test.describe("GR-35 website crawl", () => {
  test("add a site, read its pages, remove one, exclude a path, crawl again", async ({ page, workspace }) => {
    const site = await startSite();
    try {
      await page.goto(`/w/${workspace.slug}/knowledge`);
      await page.getByRole("button", { name: "Add knowledge" }).first().click();
      await page.getByRole("menuitem", { name: "Website" }).click();
      const form = page.getByRole("form", { name: "Add a website" });
      await form.getByLabel("Website address").fill(site.url);
      await form.getByRole("button", { name: "Add" }).click();

      // The row appears at once and fills in while the crawl runs (the list polls).
      const row = page.getByRole("row").filter({ hasText: "127.0.0.1" }).first();
      await expect(row).toBeVisible();
      await expect(row.getByText("4 pages")).toBeVisible({ timeout: 90_000 });
      await expect(row.getByText("Ready").first()).toBeVisible({ timeout: 90_000 });

      // robots.txt was read and its Disallow respected.
      expect(site.hits.get("/robots.txt")).toBeGreaterThan(0);
      expect(site.hits.get("/private/secret")).toBeUndefined();

      // The pages open under the row.
      await row.getByRole("button", { name: /Show pages of/ }).click();
      const pages = page.getByTestId(/^site-pages-/);
      await expect(pages.getByText("Shipping policy")).toBeVisible();
      await expect(pages.getByText("/blog/first")).toBeVisible();
      await expect(pages.getByText("/private/secret")).toHaveCount(0);
      await expect(pages.locator("li[data-status=done]")).toHaveCount(4, { timeout: 60_000 });

      // Remove a page: asked first, then it stays listed as Removed.
      await pages.getByRole("button", { name: "Actions for /returns" }).click();
      await page.getByRole("menuitem", { name: "Remove page" }).click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Remove" }).click();
      await expect(pages.locator("li[data-status=removed]")).toHaveCount(1);

      // Exclude a path: its pages go and the path is listed.
      await pages.getByLabel("Path to exclude").fill("/blog");
      await pages.getByRole("button", { name: "Exclude" }).click();
      await expect(pages.locator("li[data-status=excluded]")).toHaveCount(1);
      await expect(pages.getByRole("button", { name: "Stop excluding /blog" })).toBeVisible();

      // Crawl again: the changed page is fetched; the removed and excluded pages are not asked for.
      site.pages.set("/shipping", article("Shipping policy", "Shipping to the UAE, India and Singapore"));
      site.hits.clear();
      await pages.getByRole("button", { name: "Crawl now" }).click();
      await expect(pages.getByRole("button", { name: "Crawling" })).toBeVisible();
      await expect(pages.getByRole("button", { name: "Crawl now" })).toBeVisible({ timeout: 90_000 });
      await expect.poll(() => site.hits.get("/shipping") ?? 0, { timeout: 60_000 }).toBeGreaterThan(0);
      expect(site.hits.get("/returns")).toBeUndefined();
      expect(site.hits.get("/blog/first")).toBeUndefined();
    } finally {
      site.server.close();
    }
  });

  test("the site and its pages read at 375 px", async ({ page, workspace }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    const site = await startSite();
    try {
      await page.goto(`/w/${workspace.slug}/knowledge`);
      await page.getByRole("button", { name: "Add knowledge" }).first().click();
      await page.getByRole("menuitem", { name: "Website" }).click();
      const form = page.getByRole("form", { name: "Add a website" });
      await form.getByLabel("Website address").fill(site.url);
      await form.getByRole("button", { name: "Add" }).click();

      const row = page.getByRole("row").filter({ hasText: "127.0.0.1" }).first();
      await expect(row.getByText("Ready").first()).toBeVisible({ timeout: 90_000 });
      await row.getByRole("button", { name: /Show pages of/ }).click();
      const pages = page.getByTestId(/^site-pages-/);
      await expect(pages.getByRole("button", { name: "Crawl now" })).toBeVisible();
      await expect(pages.getByLabel("Path to exclude")).toBeVisible();

      // Nothing sideways: the page never scrolls horizontally.
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    } finally {
      site.server.close();
    }
  });

  test("an address that isn't http or https is refused", async ({ api, workspace }) => {
    await expect(
      api.call("POST", `/v1/w/${workspace.id}/knowledge-sources`, { type: "site", url: "ftp://maple.example/" }),
    ).rejects.toThrow();
  });
});
