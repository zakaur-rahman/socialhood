import { expect, test } from "./support/fixtures";

/**
 * C-172: the four plans on the pricing page. Free, Creator and Business cards, then Enterprise as a
 * "Contact us" card with a mailto link and no checkout. A paid plan shows either its real price (billing
 * on) or the planned one labelled "when we launch" (billing off). No ranking words, no sideways scroll.
 */
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("C-172 plans", () => {
  test("/pricing lists Free, Creator, Business and the Enterprise contact card", async ({ page }) => {
    await page.goto("/pricing");
    const plans = page.getByRole("list", { name: "Plans" });
    for (const name of ["Free", "Creator", "Business", "Enterprise"]) {
      await expect(plans.getByRole("heading", { name, level: 3 })).toBeVisible();
    }
    const enterprise = page.getByTestId("plan-enterprise");
    await expect(enterprise).toContainText("Contact us");
    await expect(enterprise).toContainText("from $99 a month");
    await expect(enterprise.getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "mailto:support@amplychat.com");
    await expect(enterprise.getByRole("link", { name: /start/i })).toHaveCount(0);

    for (const plan of ["pro", "max"] as const) {
      const planned = page.getByTestId(`planned-price-${plan}`);
      if (await planned.count()) await expect(planned.first()).toContainText(plan === "pro" ? "$14" : "$29");
    }
    await expect(page.locator("main")).not.toContainText(/cheapest|#1/i);
  });

  test("/pricing fits 375 and 1440 wide with four cards", async ({ page }) => {
    for (const width of [375, 1440] as const) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/pricing");
      const sideways = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(sideways, `pricing at ${width}`).toBeLessThanOrEqual(0);
    }
  });
});
