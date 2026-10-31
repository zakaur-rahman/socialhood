import { expect, test } from "./support/fixtures";

/**
 * C-163 (gloss), signed out: the glossary index (A–Z, the filter island, no script needed for the
 * list), a term page (definition first, DefinedTerm, sources) and Manychat alternatives (ItemList,
 * alphabetical, the trademark note), with no sideways scroll at 375 and 1280 px.
 */
test.use({ storageState: { cookies: [], origins: [] } });

async function jsonLdTypes(page: import("@playwright/test").Page): Promise<string[]> {
  const blocks = await page.locator('script[type="application/ld+json"]').allTextContents();
  return blocks.map((text) => (JSON.parse(text) as { "@type": string })["@type"]);
}

test.describe("C-163 glossary", () => {
  test("the index lists every term, jumps by letter and filters", async ({ page }) => {
    await page.goto("/glossary");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Meta messaging glossary");
    expect(await jsonLdTypes(page)).toEqual(expect.arrayContaining(["BreadcrumbList", "DefinedTermSet"]));
    const terms = page.locator("[data-term]");
    const total = await terms.count();
    expect(total).toBeGreaterThanOrEqual(20);
    await page.getByRole("link", { name: "Letter P" }).click();
    await expect(page).toHaveURL(/#terms-p$/);
    await page.getByRole("searchbox", { name: "Find a term" }).fill("window");
    await expect(page.locator("[data-term]:visible")).not.toHaveCount(total);
    await expect(page.getByText(/of \d+ terms/)).toBeVisible();
    await page.getByRole("button", { name: "Instagram" }).click();
    await expect(page.getByRole("button", { name: "Instagram" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("searchbox", { name: "Find a term" }).fill("");
    await page.getByRole("button", { name: "All" }).click();
    await expect(page.locator("[data-term]:visible")).toHaveCount(total);
  });

  test("the list is whole without script", async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto("/glossary");
    await expect(page.locator("[data-term]:visible")).toHaveCount(await page.locator("[data-term]").count());
    await expect(page.getByRole("searchbox")).toHaveCount(0);
    await context.close();
  });

  test("a term opens with its definition, Meta's sources and how Amplychat handles it", async ({ page }) => {
    await page.goto("/glossary/private-replies");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Private replies");
    await expect(page.locator("[data-definition]")).toContainText("A private reply is a direct message");
    await expect(page.getByRole("heading", { level: 2, name: "How Amplychat handles it" })).toBeVisible();
    await expect(page.locator('a[href^="https://developers.facebook.com/"]').first()).toBeVisible();
    expect(await jsonLdTypes(page)).toEqual(expect.arrayContaining(["BreadcrumbList", "DefinedTerm"]));
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/glossary\/private-replies$/);
  });

  test("an unknown term is a 404", async ({ page }) => {
    const response = await page.goto("/glossary/not-a-term");
    expect(response?.status()).toBe(404);
  });
});

test.describe("C-163 Manychat alternatives", () => {
  test("lists the tools alphabetically, links each comparison and notes the trademarks", async ({ page }) => {
    await page.goto("/compare/manychat-alternatives");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    expect(await jsonLdTypes(page)).toEqual(expect.arrayContaining(["BreadcrumbList", "ItemList"]));
    await expect(page.getByText(/The order isn.t a ranking/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Amplychat vs Wati" })).toHaveAttribute("href", "/compare/wati");
    await expect(page.getByText(/are trademarks of their owners/)).toBeVisible();
    await page.goto("/compare");
    await expect(page.getByRole("link", { name: "Manychat alternatives" }).first()).toHaveAttribute("href", "/compare/manychat-alternatives");
  });
});

test.describe("C-163 no sideways scroll", () => {
  for (const width of [375, 1280]) {
    for (const path of ["/glossary", "/glossary/24-hour-messaging-window", "/compare/manychat-alternatives"]) {
      test(`${path} at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(path);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow).toBeLessThanOrEqual(0);
      });
    }
  }
});
