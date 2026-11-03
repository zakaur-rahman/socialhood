import { expect, test } from "./support/fixtures";

/**
 * C-174: the Monthly / 6 months switch on the pricing page, and Agency in the full compare table. The
 * e2e stack sets no six-month or Agency product, so Agency shows its planned six-month price; Creator
 * and Business show a six-month price only if they aren't on sale, and never offer one otherwise.
 */
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("C-174 six-month plans", () => {
  test("/pricing switches to 6 months, and Agency stays Coming soon with Contact us", async ({ page }) => {
    await page.goto("/pricing");
    const agency = page.getByTestId("plan-agency");
    await expect(agency).toContainText("$70");

    await page.getByRole("radio", { name: "6 months" }).click();
    await expect(agency).toContainText("$315 every 6 months");
    await expect(agency).toContainText("($52.50 a month), save 25%");
    await expect(agency).toContainText("Coming soon");
    await expect(agency.getByRole("link", { name: "Contact us" })).toHaveAttribute("href", "mailto:support@amplychat.com");
    await expect(page.getByTestId("need-more")).toContainText("Need more?");

    await page.getByRole("radio", { name: "Monthly" }).click();
    await expect(agency).toContainText("$70");
  });

  test("the compare table has an Agency column, and six-month plans stay out of the structured data", async ({ page }) => {
    await page.goto("/pricing");
    const table = page.getByRole("region", { name: "Accounts and team" });
    await expect(table.getByRole("columnheader", { name: "Agency" })).toBeVisible();
    const jsonLd = await page.locator('script[type="application/ld+json"]').allTextContents();
    expect(jsonLd.join(" ")).not.toMatch(/every 6 months|six.month/i);
  });
});
