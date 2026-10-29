import { expect, test } from "./support/fixtures";

/**
 * The public site's shell (C-157): the phone menu closes on a tap outside it and holds one "Start
 * free" (the bar's); tablets get the section links in the bar; the bar gains its scrolled state.
 */
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("site shell", () => {
  test("the phone menu closes on an outside tap and adds only Sign in", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    const toggle = page.getByRole("button", { name: "Open menu" });
    await toggle.click();
    const menu = page.getByRole("navigation", { name: "Menu" });
    await expect(menu).toBeVisible();
    await expect(menu.getByRole("link", { name: "Sign in" })).toBeVisible();
    await expect(menu.getByRole("link", { name: "Start free" })).toHaveCount(0);
    // The panel opens with a short scale-in; measure once it has settled.
    await menu.evaluate((el) => Promise.all(el.getAnimations({ subtree: true }).map((animation) => animation.finished)));
    // Touch targets: the menu's links are 48 px, the bar's Start free 44 px.
    const linkBox = await menu.getByRole("link", { name: "Pricing" }).boundingBox();
    expect(linkBox?.height).toBeGreaterThanOrEqual(48);
    const cta = await page.locator("header .nav-r").getByRole("link", { name: "Start free" }).boundingBox();
    expect(cta?.height).toBeGreaterThanOrEqual(44);

    await page.mouse.click(180, 700);
    await expect(page.getByRole("button", { name: "Open menu" })).toHaveAttribute("aria-expanded", "false");
  });

  test("a tablet shows the section links in the bar, on one line", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link", { name: "Guides" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open menu" })).toBeHidden();
    const height = await nav.evaluate((el) => el.getBoundingClientRect().height);
    expect(height).toBeLessThanOrEqual(48);
  });

  test("the bar marks itself scrolled once the page moves", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/pricing");
    const header = page.locator("header.nav");
    await expect(header).not.toHaveAttribute("data-scrolled", "");
    await page.evaluate(() => window.scrollTo(0, 600));
    await expect(header).toHaveAttribute("data-scrolled", "");
  });
});
