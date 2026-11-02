import { expect, test } from "./support/fixtures";

// C-171: the plan stays on top; Usage (the default) and Billing are tabs.
test.describe("C-171 billing and usage tabs", () => {
  test("Usage opens first, Billing has the plans and history, and the address keeps the tab", async ({ page, workspace }) => {
    await page.goto(`/w/${workspace.slug}/settings/billing`);
    await expect(page.getByRole("tab", { name: /Usage/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("list", { name: "Usage" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Compare plans" })).toHaveCount(0);
    await page.screenshot({ path: "test-results/e2e/c171-usage-1280.png" });

    await page.getByRole("tab", { name: /Billing/ }).click();
    await expect(page).toHaveURL(/\/settings\/billing\?tab=billing$/);
    await expect(page.getByRole("heading", { name: "Compare plans" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Payment history" })).toBeVisible();
    await page.screenshot({ path: "test-results/e2e/c171-billing-1280.png" });

    await page.reload();
    await expect(page.getByRole("tab", { name: /Billing/ })).toHaveAttribute("aria-selected", "true");

    await page.setViewportSize({ width: 375, height: 800 });
    await expect(page.getByRole("tab", { name: /Usage/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
    await page.screenshot({ path: "test-results/e2e/c171-billing-375.png" });
  });
});
