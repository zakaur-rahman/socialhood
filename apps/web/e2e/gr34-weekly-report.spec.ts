import { expect, test } from "./support/fixtures";

/**
 * GR-34 weekly report. A finished week can't be seeded through the API (messages arrive now), so
 * the spec checks what a member sees against GET …/reports/weekly for the same week: the tiles
 * show the API's numbers, a week with no figure shows a dash and a gap note rather than 0, the
 * week is in the address, the picker moves between weeks, a bad week is explained, Home links to
 * the report, and at 375 px the page does not scroll sideways.
 */
type Metric = {
  key: string;
  label: string;
  unit: "count" | "percent" | "seconds";
  value: number | null;
  series: { week_start: string; value: number | null }[];
};
type Report = { week_start: string; weeks: string[]; metrics: Metric[]; series_weeks: number };

const number = new Intl.NumberFormat("en-US");

test.describe("GR-34 weekly report", () => {
  test("the latest week shows the API's numbers, with gaps said and not zeroed", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const report = await api.call<Report>("GET", `/v1/w/${workspace.id}/reports/weekly`);
    expect(report.series_weeks).toBe(8);
    expect(report.weeks[0]).toBe(report.week_start);

    await page.goto(`/w/${workspace.slug}/reports`);
    await expect(page.getByRole("heading", { level: 1, name: "Weekly report" })).toBeVisible();
    await expect(page.getByTestId("report-span")).toContainText("Monday to Sunday");

    for (const metric of report.metrics) {
      const tile = page.locator(`[data-metric="${metric.key}"]`).first();
      await expect(tile).toBeVisible();
      const shown = tile.getByTestId("metric-value");
      if (metric.value === null) await expect(shown).toHaveText("—");
      else if (metric.unit === "count") await expect(shown).toHaveText(number.format(Math.round(metric.value)));
      // A chart under every tile, with the weeks that have no figure named.
      await expect(tile.getByTestId("series-chart")).toBeVisible();
      const gaps = metric.series.filter((p) => p.value === null).length;
      if (gaps > 0) await expect(tile.getByTestId("series-gaps")).toContainText(/without data/);
      else await expect(tile.getByTestId("series-gaps")).toHaveCount(0);
    }
    await expect(page.getByTestId("report-note")).toContainText("aren't counted here yet");
    await expect(page.getByTestId("visual-metric-comparison")).toBeVisible();
  });

  test("the week is in the address and the picker moves between weeks", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const report = await api.call<Report>("GET", `/v1/w/${workspace.id}/reports/weekly`);
    const earlier = report.weeks[1];

    await page.goto(`/w/${workspace.slug}/reports?week=${earlier}`);
    await expect(page.getByRole("combobox", { name: "Week" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Later week" })).toBeEnabled();

    await page.getByRole("button", { name: "Later week" }).click();
    await expect(page).toHaveURL(new RegExp(`reports\\?week=${report.week_start}$`));
    await expect(page.getByRole("button", { name: "Later week" })).toBeDisabled();

    await page.getByRole("button", { name: "Earlier week" }).click();
    await expect(page).toHaveURL(new RegExp(`reports\\?week=${earlier}$`));
    const asked = await api.call<Report>("GET", `/v1/w/${workspace.id}/reports/weekly?week=${earlier}`);
    expect(asked.week_start).toBe(earlier);
  });

  test("a week that can't be shown is explained and the latest one is one click away", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    // 2020-01-07 was a Tuesday.
    await page.goto(`/w/${workspace.slug}/reports?week=2020-01-07`);
    await expect(page.getByText("That isn't a week the report can show.")).toBeVisible();
    await page.getByRole("button", { name: "Show the latest week" }).click();
    await expect(page.getByTestId("weekly-report")).toBeVisible();
  });

  test("Home links to the report", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.goto(`/w/${workspace.slug}/home`);
    await page.getByRole("link", { name: "Weekly report" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/reports$`));
    await expect(page.getByRole("heading", { level: 1, name: "Weekly report" })).toBeVisible();
  });

  test("at 375 px the tiles are one column and the page does not scroll sideways", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`/w/${workspace.slug}/reports`);
    await expect(page.getByTestId("weekly-report")).toBeVisible();

    const first = await page.locator("[data-metric]").first().boundingBox();
    const second = await page.locator("[data-metric]").nth(1).boundingBox();
    expect(first && second && second.y > first.y).toBe(true); // stacked, not side by side
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    await expect(page.getByRole("combobox", { name: "Week" })).toBeVisible();
  });
});
