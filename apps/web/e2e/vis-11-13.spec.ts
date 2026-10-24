import type { Page } from "@playwright/test";

import { expect, test, unique } from "./support/fixtures";

/**
 * VIS-11 and VIS-13 in Ask: a visual's range and platform controls ask the same question again as a
 * structured follow-up (words in the bubble, never ids or a data query), and an answer that cites
 * the weekly report links to it. The fake model calls no tools, so a seeded run
 * (POST /__e2e/…/agent-runs with `trend`, and `reportWeek`) stands in for the first answer.
 *
 * Needs the stack to run with AGENT_VISUALS_ENABLED=true (scripts/e2e-stack.mjs sets it).
 */

type Run = { id: string; request: string; hints?: { range_days?: number; platform?: string } | null };

/** Open the Ask page on the thread whose question carries `tag`. */
async function openThread(page: Page, slug: string, tag: string, request: string) {
  await page.goto(`/w/${slug}/ask`);
  await page.getByRole("navigation", { name: "Threads" }).getByText(tag).click();
  await expect(page.getByRole("article", { name: `Question: ${request}` })).toBeVisible({ timeout: 30_000 });
}

/** The latest finished week's Monday, as the report page counts it (UTC is close enough: it is a link, not a figure). */
function lastFinishedMonday(): string {
  const now = new Date();
  const monday = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7) - 7);
  return monday.toISOString().slice(0, 10);
}

test.describe("VIS-11 and VIS-13", () => {
  test("changing the range asks again in the thread, in words, for a run's credits", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("controls");
    const request = `How has my reach moved? ${tag}`;
    const seeded = await api.agentRun(workspace.id, {
      request,
      answer: "Reach is steady.",
      accountId: account.id,
      visual: true,
      trend: true,
      days: 14,
    });
    await openThread(page, workspace.slug, tag, request);

    const controls = page.getByTestId("visual-controls").first();
    await expect(controls).toBeVisible();
    await expect(controls.getByTestId("controls-note")).toContainText("About 2 to 4 AI credits");

    await controls.getByRole("radio", { name: "Last 90 days" }).click();
    const bubble = page.getByRole("article", { name: "Question: Same, for the last 90 days" });
    await bubble.first().waitFor({ timeout: 30_000 });

    // The follow-up is a run in the same thread whose hints are the whitelisted choice.
    const thread = await api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/agent/runs?thread_id=${seeded.thread_id}`);
    const followUp = thread.items.find((run) => run.request === "Same, for the last 90 days");
    expect(followUp?.hints).toEqual({ range_days: 90 });
  });

  test("an answer that cites the weekly report links to that week", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("report");
    const request = `How did last week go? ${tag}`;
    const week = lastFinishedMonday();
    await api.agentRun(workspace.id, {
      request,
      answer: "Last week was steady [1].",
      accountId: account.id,
      reportWeek: week,
    });
    await openThread(page, workspace.slug, tag, request);
    const link = page.getByRole("link", { name: /Weekly report/ }).first();
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", new RegExp(`/w/${workspace.slug}/reports\?week=${week}&account=${account.id}`));
  });
});
