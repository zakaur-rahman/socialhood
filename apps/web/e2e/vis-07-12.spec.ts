import type { Page } from "@playwright/test";

import type { Api } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * VIS-07 to VIS-12 in Ask: the trend line, the lead list with its "Prepare replies" follow-up, the
 * conversation table, and progressive visuals. The fake model calls no tools, so the API's seed
 * routes store finished runs whose steps are the real tools' results (POST /__e2e/…/agent-runs with
 * `trend`, and …/agent-leads). The spec checks what the member sees against the API's own data.
 *
 * Needs the stack to run with AGENT_VISUALS_ENABLED=true (scripts/e2e-stack.mjs sets it).
 */

type Contact = { id: string; name: string; username: string | null; conversation_id: string | null };
type Run = { id: string; request: string; hints?: { reply_conversation_ids?: string[] } | null; action_cards: { kind: string; route: string; label: string }[] };

const SCORES = [90, 60, 30];

/** Open the Ask page on the thread whose question carries `tag` (the history cuts long titles). */
async function openThread(page: Page, slug: string, tag: string, request: string) {
  await page.goto(`/w/${slug}/ask`);
  await page.getByRole("navigation", { name: "Threads" }).getByText(tag).click();
  await expect(page.getByRole("article", { name: `Question: ${request}` })).toBeVisible({ timeout: 30_000 });
}

/** Three customers who wrote last, so all of them wait for a reply; returns them by username. */
async function waitingLeads(api: Api, wid: string, accountId: string, tag: string): Promise<{ username: string; contact: Contact }[]> {
  const names = SCORES.map((_, i) => `e2e_vis_${tag.replace(/\W+/g, "_")}_${i}`);
  for (const username of names) {
    await api.inbound(wid, { accountId, kind: "dm", text: "How much is it?", fromId: username, fromUsername: username });
  }
  const found: { username: string; contact: Contact }[] = [];
  await expect
    .poll(
      async () => {
        found.length = 0;
        for (const username of names) {
          const list = await api.call<{ items: Contact[] }>("GET", `/v1/w/${wid}/contacts?q=${username}`);
          const contact = list.items.find((c) => c.username === username);
          if (contact?.conversation_id) found.push({ username, contact });
        }
        return found.length;
      },
      { timeout: 30_000 },
    )
    .toBe(names.length);
  return found;
}

test.describe("VIS-07 to VIS-12", () => {
  test("a trend draws the reach line with its facts and a text version", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("trend");
    const request = `How has my reach moved? ${tag}`;
    await api.agentRun(workspace.id, {
      request,
      answer: "Reach is steady.",
      accountId: account.id,
      visual: true,
      trend: true,
      days: 14,
    });
    await openThread(page, workspace.slug, tag, request);
    const chart = page.getByTestId("visual-trend");
    await expect(chart).toBeVisible();
    await expect(chart.getByTestId("trend-line")).toHaveCount(1); // every day has a reading: one run
    await expect(chart.getByTestId("trend-svg")).toHaveAttribute("aria-label", /^Reach by day, /);
    await expect(chart.getByTestId("trend-facts")).toContainText("Highest");
    // The text version: one row per day.
    await expect(chart.getByTestId("trend-table").locator("tbody tr")).toHaveCount(14);

    await page.setViewportSize({ width: 375, height: 800 });
    await expect(chart).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });

  test("the lead list is best score first, opens the conversation and is a table too", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("leads");
    const request = `Which leads are waiting for me? ${tag}`;
    const leads = await waitingLeads(api, workspace.id, account.id, tag);
    const scores = Object.fromEntries(leads.map((l, i) => [l.username, SCORES[i]]));
    await api.agentLeads(workspace.id, { request, answer: "Three leads are waiting.", scores });

    await openThread(page, workspace.slug, tag, request);
    const list = page.getByTestId("visual-lead-list");
    await expect(list).toBeVisible();
    const rows = list.getByTestId("lead-row");
    await expect(rows).toHaveCount(3);
    await expect(rows.nth(0).getByTestId("lead-score")).toHaveText("Score 90");
    await expect(rows.nth(1).getByTestId("lead-score")).toHaveText("Score 60");
    await expect(rows.nth(2).getByTestId("lead-score")).toHaveText("Score 30");
    await expect(rows.nth(0)).toContainText(leads[0].contact.name);

    // The same conversations as a table, with the lead score right-aligned.
    const table = page.getByTestId("visual-table");
    await expect(table).toBeVisible();
    await expect(table.getByTestId("table-row")).toHaveCount(3);

    // A row opens its conversation.
    await rows.nth(0).getByRole("link").click();
    await expect(page).toHaveURL(new RegExp(`/inbox/${leads[0].contact.conversation_id}`));
  });

  test("Prepare replies asks for one draft per lead and sends nothing", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("prep");
    const request = `Which leads are waiting for me? ${tag}`;
    const leads = await waitingLeads(api, workspace.id, account.id, tag);
    const scores = Object.fromEntries(leads.map((l, i) => [l.username, SCORES[i]]));
    const seeded = await api.agentLeads(workspace.id, { request, answer: "Three leads are waiting.", scores });
    expect(seeded.reply_ids).toHaveLength(3);

    await openThread(page, workspace.slug, tag, request);
    const list = page.getByTestId("visual-lead-list");
    await expect(list.getByText("Drafts a reply for the top 3 leads. Nothing is sent.")).toBeVisible();
    await list.getByRole("button", { name: "Prepare replies" }).click();

    // The follow-up is a new question in the same thread: words in the bubble, ids only in its hints.
    const bubble = page.getByRole("article", { name: "Question: Prepare replies for these leads" });
    await expect(bubble).toBeVisible({ timeout: 30_000 });
    const asked = await api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/agent/runs?thread_id=${seeded.thread_id}`);
    const followUp = asked.items.find((run) => run.request === "Prepare replies for these leads");
    expect(followUp).toBeDefined();
    expect([...(followUp?.hints?.reply_conversation_ids ?? [])].sort()).toEqual([...seeded.reply_ids].sort());
    for (const id of seeded.reply_ids) expect(followUp?.request).not.toContain(id);
    // Drafts are never sent: no outbound message exists for any of these conversations.
    for (const { contact } of leads) {
      const messages = await api.call<{ items: { direction: string }[] }>(
        "GET",
        `/v1/w/${workspace.id}/conversations/${contact.conversation_id}/messages`,
      );
      expect(messages.items.every((m) => m.direction === "inbound")).toBe(true);
    }
  });

  test("the drafts come back as one card per lead that opens the conversation", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const tag = unique("drafts");
    const request = `Which leads are waiting for me? ${tag}`;
    const leads = await waitingLeads(api, workspace.id, account.id, tag);
    const scores = Object.fromEntries(leads.map((l, i) => [l.username, SCORES[i]]));
    const seeded = await api.agentLeads(workspace.id, {
      request,
      answer: "Three leads are waiting.",
      scores,
      drafts: true,
    });
    expect(seeded.follow_up_run_id).not.toBeNull();

    await openThread(page, workspace.slug, tag, request);
    const cards = page.getByTestId("action-schedule_message");
    await expect(cards).toHaveCount(3, { timeout: 30_000 });
    await expect(cards.nth(0)).toContainText(`Schedule a reply to ${leads[0].contact.name}`);
    // The lead list belongs to the first question, so only the latest answer offers the button.
    await expect(page.getByRole("button", { name: "Prepare replies" })).toHaveCount(0);

    await cards.nth(0).getByRole("button", { name: /^Open/ }).click();
    await expect(page).toHaveURL(new RegExp(`/inbox/${leads[0].contact.conversation_id}\\?schedule=1`));
  });
});
