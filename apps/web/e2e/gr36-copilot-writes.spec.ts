import type { Page } from "@playwright/test";

import { expect, test, unique } from "./support/fixtures";

/**
 * GR-36 Copilot write actions. The fake model calls no tools, so the API's seed route stores a
 * finished run whose draft step called propose_flow / propose_segment through the real tool and
 * the action gateway: a pending approval and its card. The spec checks what a member sees and what
 * the API holds: nothing is saved while it waits, approving saves a DRAFT automation or a segment
 * through the normal services, rejecting saves nothing, and "Waiting for you" decides the same
 * approvals.
 */

type Approval = { id: string; status: string; can_decide: boolean; outcome: { ok: boolean; resource_id: string | null } | null };
type Automation = { id: string; name: string; status: string };
type Segment = { id: string; name: string };

/** Open the Ask page on the thread whose question carries `tag` (the history cuts long titles). */
async function openThread(page: Page, slug: string, tag: string, request: string) {
  await page.goto(`/w/${slug}/ask`);
  await page.getByRole("navigation", { name: "Threads" }).getByText(tag).click();
  await expect(page.getByRole("article", { name: `Question: ${request}` })).toBeVisible({ timeout: 30_000 });
}

test.describe("GR-36 copilot writes", () => {
  test("a proposed flow waits, then approving saves a draft automation that is not switched on", async ({
    page,
    api,
    sandbox,
  }) => {
    const { workspace } = sandbox;
    const tag = unique("flow");
    const request = `When someone comments PRICE send them the price list ${tag}`;
    const name = `Price list ${tag}`;
    const proposal = await api.agentProposal(workspace.id, { request, kind: "flow", name });

    const automations = () => api.call<{ items: Automation[] }>("GET", `/v1/w/${workspace.id}/automations`);
    expect((await automations()).items.filter((a) => a.name === name)).toHaveLength(0);

    await openThread(page, workspace.slug, tag, request);
    const card = page.getByRole("region", { name: "Automation proposal" });
    await expect(card).toBeVisible();
    await expect(card.getByRole("heading", { name: `New automation: ${name}` })).toBeVisible();
    await expect(card.getByRole("list", { name: "What will happen" })).toContainText("price list");
    await expect(card.getByTestId("approval-status")).toHaveText("Waiting for approval");
    // Waiting means nothing is saved.
    expect((await automations()).items.filter((a) => a.name === name)).toHaveLength(0);

    await card.getByRole("button", { name: /Approve/ }).click();
    await expect(card.getByTestId("approval-result")).toContainText("Saved the draft automation", { timeout: 30_000 });
    await expect(card.getByTestId("approval-status")).toHaveText("Approved");

    const saved = (await automations()).items.filter((a) => a.name === name);
    expect(saved).toHaveLength(1);
    expect(saved[0].status).toBe("draft"); // approving never switches it on

    const approvals = await api.call<{ items: Approval[] }>(
      "GET",
      `/v1/w/${workspace.id}/agent/approvals?status=all&run_id=${proposal.run_id}`,
    );
    expect(approvals.items.map((a) => [a.id, a.status, a.outcome?.resource_id])).toEqual([
      [proposal.approval_id, "approved", saved[0].id],
    ]);

    await card.getByRole("button", { name: "Open the automation" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/automations/${saved[0].id}$`));
    await expect(page.getByText(name).first()).toBeVisible({ timeout: 30_000 });
  });

  test("a proposed segment is decided from Waiting for you", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    await api.call("POST", `/v1/w/${workspace.id}/tags`, { name: "vip" });
    const tag = unique("seg");
    const request = `Save a segment of vip people who gave their email ${tag}`;
    const name = `VIPs ${tag}`;
    await api.agentProposal(workspace.id, { request, kind: "segment", name, tag: "vip" });

    const segments = () => api.call<{ items: Segment[] }>("GET", `/v1/w/${workspace.id}/contact-segments`);
    expect((await segments()).items.filter((s) => s.name === name)).toHaveLength(0);

    await openThread(page, workspace.slug, tag, request);
    const card = page.getByRole("region", { name: "Segment proposal" });
    await expect(card.getByRole("list", { name: "What will happen" })).toContainText("Has the tag vip");
    await expect(card.getByTestId("proposal-count")).toContainText("match");

    const waiting = page.getByRole("region", { name: "Waiting for you" });
    await expect(waiting).toBeVisible({ timeout: 30_000 });
    await waiting.getByRole("button", { name: /Waiting for you/ }).click();
    const item = waiting.getByTestId("waiting-item").filter({ hasText: name });
    await expect(item).toBeVisible();
    await item.getByRole("button", { name: /Approve/ }).click();

    await expect.poll(async () => (await segments()).items.some((s) => s.name === name), { timeout: 30_000 }).toBe(true);
    await expect(card.getByTestId("approval-result")).toContainText("Saved the segment", { timeout: 30_000 });
    await expect(waiting).toHaveCount(0); // nothing left waiting
  });

  test("rejecting saves nothing", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const tag = unique("reject");
    const request = `Make an automation for PRICE comments ${tag}`;
    const name = `Rejected ${tag}`;
    const proposal = await api.agentProposal(workspace.id, { request, kind: "flow", name });

    await openThread(page, workspace.slug, tag, request);
    const card = page.getByRole("region", { name: "Automation proposal" });
    await card.getByRole("button", { name: /Reject/ }).click();
    await expect(card.getByTestId("approval-result")).toContainText("Nothing was saved", { timeout: 30_000 });
    await expect(card.getByTestId("approval-status")).toHaveText("Rejected");
    await expect(card.getByRole("button", { name: /Approve/ })).toHaveCount(0);

    const list = await api.call<{ items: Automation[] }>("GET", `/v1/w/${workspace.id}/automations`);
    expect(list.items.filter((a) => a.name === name)).toHaveLength(0);
    const rows = await api.call<{ items: Approval[] }>(
      "GET",
      `/v1/w/${workspace.id}/agent/approvals?status=all&run_id=${proposal.run_id}`,
    );
    expect(rows.items.map((a) => a.status)).toEqual(["rejected"]);
  });

  test("the card fits a 375 px phone", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const tag = unique("narrow");
    const request = `Build a PRICE automation ${tag}`;
    await api.agentProposal(workspace.id, { request, kind: "flow", name: `Narrow ${tag}` });
    await openThread(page, workspace.slug, tag, request);
    await page.setViewportSize({ width: 375, height: 800 });
    const card = page.getByRole("region", { name: "Automation proposal" });
    await expect(card.getByRole("button", { name: /Approve/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});
