import { expect, test } from "./support/fixtures";

/**
 * GR-10 A Live comment with the keyword gets the private reply, recorded as a run. One that
 * arrives after the broadcast has ended is recorded as skipped (the Live ended) and nothing is
 * sent. The editor offers the Live scope.
 */
type Run = { id: string; result: string; error_code?: string | null };

test.describe("GR-10 live comments", () => {
  test("a Live comment with the keyword gets a private reply", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `live${Date.now().toString(36)}`;
    const automation = await api.liveAutomation(workspace.id, account.id, keyword, "Here is the link from the Live!");
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "live_comment",
      text: `${keyword} please`,
      fromId: `e2e_gr10_${Date.now().toString(36)}`,
    });

    await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 45_000 }).toBe("sent");
  });

  test("a Live comment that arrives after the Live ended is skipped", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `late${Date.now().toString(36)}`;
    const automation = await api.liveAutomation(workspace.id, account.id, keyword, "Too late for this one.");
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "live_comment",
      text: keyword,
      fromId: `e2e_gr10b_${Date.now().toString(36)}`,
      ageSeconds: 3600,
    });

    await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 30_000 }).toBe("skipped_expired");
  });

  test("the editor offers the Live scope", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: "Live editor",
      social_account_id: account.id,
    });
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    await page.getByRole("radio", { name: "Instagram comment keyword" }).click();
    await page.getByRole("radio", { name: "Live", exact: true }).click();
    await expect(page.getByText("On Lives")).toBeVisible();
  });
});
