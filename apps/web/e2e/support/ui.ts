import type { Locator, Page } from "@playwright/test";

/** Opens the date picker's calendar, pages to the month of `day` ("YYYY-MM-DD") and clicks it. */
export async function pickDay(page: Page, trigger: Locator, day: string): Promise<void> {
  await trigger.click();
  const cell = page.locator(`td[data-day="${day}"]:not([data-outside])`);
  for (let hops = 0; hops < 2 && (await cell.count()) === 0; hops++) {
    await page.getByRole("button", { name: /next month/i }).click();
  }
  await cell.getByRole("button").click();
}
