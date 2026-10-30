import { expect, test } from "./support/fixtures";

/**
 * GR-37 go-to-market pages, with the C-156 comparisons and the /compare hub. They are public, so
 * each is visited signed out: the h1, the title, the canonical link, an Open Graph title, the
 * sitemap entry, and no sideways page scroll at phone width. The comparison tables scroll inside
 * their own box, never the page.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const PAGES = [
  { path: "/pricing", h1: "Start free, upgrade when you grow", title: "Pricing" },
  { path: "/switch-from-manychat", h1: "Move your Instagram automations from Manychat", title: "Switch from Manychat" },
  { path: "/compare/manychat", h1: "Amplychat vs Manychat", title: "Amplychat vs Manychat" },
  { path: "/compare/interakt", h1: "Amplychat vs Interakt", title: "Amplychat vs Interakt" },
  { path: "/compare/linkdm", h1: "Amplychat vs LinkDM", title: "Amplychat vs LinkDM" },
  { path: "/compare/instantdm", h1: "Amplychat vs InstantDM", title: "Amplychat vs InstantDM" },
  { path: "/compare/inro", h1: "Amplychat vs Inrō", title: "Amplychat vs Inrō" },
  { path: "/compare/creatorflow", h1: "Amplychat vs CreatorFlow", title: "Amplychat vs CreatorFlow" },
  { path: "/compare/wati", h1: "Amplychat vs Wati", title: "Amplychat vs Wati" },
  { path: "/compare/aisensy", h1: "Amplychat vs AiSensy", title: "Amplychat vs AiSensy" },
  { path: "/compare/spur", h1: "Amplychat vs Spur", title: "Amplychat vs Spur" },
  { path: "/compare", h1: "How Amplychat compares", title: "How Amplychat compares" },
  { path: "/features/comment-intelligence", h1: "Know what your comments are telling you", title: "Comment intelligence for Instagram" },
  { path: "/features/ai-inbox", h1: "One inbox that answers from what you know", title: "AI inbox for Instagram, WhatsApp and web chat" },
  { path: "/features/publishing", h1: "Plan your posts where your customers reply", title: "Schedule Instagram posts and Stories" },
] as const;

test.describe("GR-37 go-to-market pages", () => {
  for (const { path, h1, title } of PAGES) {
    test(`${path} renders with its metadata`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(h1);
      await expect(page).toHaveTitle(new RegExp(title));
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", new RegExp(`${path}$`));
      await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", /Amplychat/);
      await expect(page.getByRole("link", { name: /Start free/ }).first()).toHaveAttribute("href", /\/sign-up/);
    });

    test(`${path} fits a phone`, async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 800 });
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }

  test("the comparison pages show their sources and the pricing page its limits", async ({ page }) => {
    await page.goto("/compare/interakt");
    await expect(page.getByRole("table", { name: "Amplychat and Interakt feature by feature" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Interakt pricing" })).toHaveAttribute("href", "https://www.interakt.shop/pricing/");
    await expect(page.getByText(/Interakt is a trademark of its owner\. Amplychat isn't affiliated with or endorsed by Interakt\./)).toBeVisible();

    for (const path of ["/compare/manychat", "/switch-from-manychat"]) {
      await page.goto(path);
      await expect(page.getByText(/Manychat is a trademark of its owner\. Amplychat isn't affiliated with or endorsed by Manychat\./)).toBeVisible();
    }

    // C-156: every new comparison names its competitor in the trademark and no-affiliation note.
    const competitors = [
      ["/compare/linkdm", "LinkDM"],
      ["/compare/instantdm", "InstantDM"],
      ["/compare/inro", "Inrō"],
      ["/compare/creatorflow", "CreatorFlow"],
      ["/compare/wati", "Wati"],
      ["/compare/aisensy", "AiSensy"],
      ["/compare/spur", "Spur"],
    ] as const;
    for (const [path, name] of competitors) {
      await page.goto(path);
      const note = `${name} is a trademark of its owner. Amplychat isn't affiliated with or endorsed by ${name}.`;
      await expect(page.getByRole("main").getByText(note, { exact: false })).toBeVisible();
    }

    await page.goto("/compare");
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { level: 2, name: "Instagram DM tools" })).toBeVisible();
    await expect(main.getByRole("heading", { level: 2, name: "WhatsApp platforms" })).toBeVisible();
    await expect(main.getByRole("link", { name: "Amplychat vs Wati" })).toHaveAttribute("href", "/compare/wati");

    await page.goto("/pricing");
    await expect(page.getByRole("table", { name: "WhatsApp and products" })).toBeVisible();
    await expect(page.getByRole("row", { name: /WhatsApp broadcast recipients a month/ })).toContainText("Not included");
  });

  test("C-159: the comparison table's header sticks on a wide screen, and a phone scrolls the table in its own box", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/compare/wati");
    const table = page.getByRole("table", { name: "Amplychat and Wati feature by feature" });
    await table.locator("tbody tr").nth(6).scrollIntoViewIfNeeded();
    await page.mouse.wheel(0, 300);
    const head = table.locator("thead th").first();
    await expect.poll(async () => Math.round((await head.boundingBox())?.y ?? -1)).toBeLessThanOrEqual(72);
    // Each status is a chip with its words; our column is marked.
    await expect(table.locator("thead th.ours")).toHaveText("Amplychat");
    await expect(table.locator("[data-status='not-found']").first()).toHaveText("Not found");

    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/compare/wati");
    const box = page.getByRole("region", { name: "Amplychat and Wati feature by feature" });
    const scrolls = await box.evaluate((el) => el.scrollWidth > el.clientWidth);
    expect(scrolls).toBe(true);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("C-159: /faq has a group nav, and the hub's cards are links", async ({ page }) => {
    await page.goto("/faq");
    const nav = page.getByRole("navigation", { name: "Question groups" });
    await nav.getByRole("link", { name: /^Plans and billing/ }).click();
    await expect(page).toHaveURL(/#plans$/);
    await expect(page.getByRole("heading", { level: 2, name: "Plans and billing" })).toBeInViewport();

    await page.goto("/compare");
    await page.locator(".hcard").filter({ hasText: "Amplychat vs Spur" }).click({ position: { x: 20, y: 80 } });
    await expect(page).toHaveURL(/\/compare\/spur$/);
  });

  test("the sitemap lists every page and the footer links to them", async ({ page, request }) => {
    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.ok()).toBe(true);
    const xml = await sitemap.text();
    for (const { path } of PAGES) expect(xml).toContain(`${path}</loc>`);

    await page.goto("/");
    const footer = page.getByRole("contentinfo");
    await expect(footer.getByRole("link", { name: "Switch from Manychat" })).toHaveAttribute("href", "/switch-from-manychat");
    // C-161: the bar names the business without its location, and the name closes the page, hidden.
    await expect(footer).toContainText(/© \d{4} UNCHARTD/);
    await expect(footer).not.toContainText("Bihar");
    await expect(footer.locator(".foot-word[aria-hidden]")).toHaveCount(1);
    await footer.getByRole("link", { name: "Pricing", exact: true }).click();
    await expect(page).toHaveURL(/\/pricing$/);
  });
});
