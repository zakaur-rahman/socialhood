import type { Page } from "@playwright/test";

import { expect, test, unique } from "./support/fixtures";

/**
 * GR-38 visual answers in Ask. The fake model calls no tools, so the API's seed route stores a
 * finished run whose compare_periods step holds the metric_comparison the real analytics service
 * and builder make from seeded account metrics. The spec then checks what the member sees: cards
 * whose numbers equal GET …/analytics/account-metrics, a conceptual answer without a visual, the
 * same cards at 375 px and in the Ask panel.
 *
 * Needs the stack to run with AGENT_VISUALS_ENABLED=true (scripts/e2e-stack.mjs sets it).
 */

type Figure = {
  metric: string;
  current: { value: number | null; days_known: number; days_total: number };
  previous: { value: number | null } | null;
  change_pct: number | null;
  direction: "up" | "down" | "flat" | null;
};
type Visual = { kind: string; current: { start: string; end: string }; metrics: { key: string }[] };

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const METRICS = ["reach", "interactions", "followers", "unfollows"] as const;

/** Open the Ask page on the thread whose question carries `tag` (the history cuts long titles). */
async function openThread(page: Page, slug: string, tag: string, request: string) {
  await page.goto(`/w/${slug}/ask`);
  await page.getByRole("navigation", { name: "Threads" }).getByText(tag).click();
  await expect(page.getByRole("article", { name: `Question: ${request}` })).toBeVisible({ timeout: 30_000 });
}

test.describe("GR-38 visual answers", () => {
  test("this month against last month shows cards equal to the service's figures", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("vis");
    const request = `Compare my Instagram this month with last month ${tag}`;
    const run = await api.agentRun(workspace.id, {
      request,
      answer: "Reach is up on the earlier days of the previous period.",
      accountId: account.id,
      visual: true,
      days: 14,
    });

    // The API: one metric_comparison in the run, and the service's own figures for its two periods.
    const detail = await api.call<{ visuals: Visual[] }>("GET", `/v1/w/${workspace.id}/agent/runs/${run.id}`);
    expect(detail.visuals.map((v) => v.kind)).toEqual(["metric_comparison"]);
    const { start, end } = detail.visuals[0].current;
    const query = new URLSearchParams({ since: start, until: end, compare: "previous", account_id: account.id });
    for (const metric of METRICS) query.append("metric", metric);
    const truth = await api.call<{ comparable: boolean; figures: Figure[] }>(
      "GET",
      `/v1/w/${workspace.id}/analytics/account-metrics?${query}`,
    );
    expect(truth.comparable).toBe(true);
    expect(truth.figures.map((f) => f.metric)).toEqual([...METRICS]);

    await openThread(page, workspace.slug, tag, request);
    const cards = page.getByTestId("visual-metric-comparison");
    await expect(cards).toBeVisible();
    await expect(cards.getByTestId("metric-tile")).toHaveCount(METRICS.length);

    for (const figure of truth.figures) {
      const tile = cards.locator(`[data-metric="${figure.metric}"]`);
      await expect(tile.getByTestId("metric-value")).toHaveText(number.format(figure.current.value ?? NaN));
      await expect(tile).toContainText(number.format(figure.previous?.value ?? NaN));
      if (figure.change_pct !== null && figure.direction !== "flat") {
        const sign = figure.change_pct > 0 ? "+" : "−";
        await expect(tile.getByTestId("trend")).toContainText(`${sign}${number.format(Math.abs(figure.change_pct))}%`);
      }
      // Every day has a reading in the seed: no "N of M days" note.
      await expect(tile).not.toContainText(/\d+ of \d+ days/);
    }
    // The seed has 4 unfollows a day before and 5 now: up, and that is bad news (the API's tone).
    await expect(cards.locator('[data-metric="unfollows"]').getByTestId("trend")).toHaveAttribute("data-tone", "bad");
  });

  test("a conceptual answer shows no visual", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const tag = unique("concept");
    const request = `What is a good reply rate? ${tag}`;
    await api.agentRun(workspace.id, { request, answer: "Most small businesses aim to answer within an hour." });
    await openThread(page, workspace.slug, tag, request);
    await expect(page.getByText("Most small businesses aim to answer within an hour.")).toBeVisible();
    await expect(page.getByTestId("visual")).toHaveCount(0);
  });

  test("the cards fit a 375 px phone and show in the Ask panel", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("narrow");
    const request = `Compare my Instagram this month with last month ${tag}`;
    await api.agentRun(workspace.id, {
      request,
      answer: "Reach moved against the previous period.",
      accountId: account.id,
      visual: true,
    });
    await openThread(page, workspace.slug, tag, request);
    const cards = page.getByTestId("visual-metric-comparison");
    await expect(cards).toBeVisible();

    await page.setViewportSize({ width: 375, height: 800 });
    await expect(cards).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const tile = cards.getByTestId("metric-tile").first();
    const box = await tile.boundingBox();
    expect(box).not.toBeNull();
    expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(375);
    expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);

    // The panel shows the same thread: leave the Ask page by a link (the thread stays chosen), then
    // open the panel from its button.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.getByRole("link", { name: "Home" }).first().click();
    await expect(page).toHaveURL(/\/home/);
    await page.getByRole("button", { name: "Ask Amplychat" }).first().click();
    const panel = page.getByRole("dialog", { name: "Ask Amplychat" });
    await expect(panel.getByTestId("visual-metric-comparison")).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByTestId("metric-tile").first()).toBeVisible();
  });
});
