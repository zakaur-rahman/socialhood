import { expect, test } from "./support/fixtures";

/**
 * GR-08 Opening an entry link in the sandbox (a referral with its ref, then a DM) starts the
 * link's automation and counts on the Entry links page.
 */
type Run = { id: string; result: string };
type Link = { id: string; opened_conversations: number; runs: number };

test.describe("GR-08 entry links", () => {
  test("a referral then a DM starts the link's automation and counts", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const automation = await api.entryAutomation(workspace.id, account.id, "entry_link", {
      messageText: "Welcome! Thanks for scanning.",
    });
    const code = `e2e${Date.now().toString(36)}`;
    const link = await api.entryLink(workspace.id, account.id, { name: "Shop window", automationId: automation.id, code });
    expect(link.url).toContain(`?ref=${code}`);

    const fan = `e2e_gr08_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "referral", referralSource: "link", ref: code, fromId: fan });
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi!", fromId: fan });

    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);

    await page.goto(`/w/${workspace.slug}/automations/entry-links`);
    const row = page.getByTestId("entry-link-row").first();
    await expect(row).toContainText("Shop window");
    await expect(row.getByTestId("entry-link-url")).toContainText(`?ref=${code}`);
    await expect(row.getByTestId("entry-link-opened")).toHaveText("1");
    await expect(row.getByTestId("entry-link-runs")).toHaveText("1");
  });

  test("a ref that is not a link starts nothing", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const automation = await api.entryAutomation(workspace.id, account.id, "entry_link", { messageText: "Welcome!" });
    const fan = `e2e_gr08b_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "referral", referralSource: "link", ref: "nobody", fromId: fan });
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hello", fromId: fan });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    const runs = await api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    expect(runs.items).toHaveLength(0);
  });

  test("the QR code downloads and the page offers copy", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.entryLink(workspace.id, account.id, { name: "Menu card" });
    await page.goto(`/w/${workspace.slug}/automations/entry-links`);
    const row = page.getByTestId("entry-link-row").first();
    await expect(row.getByRole("button", { name: "Copy link" })).toBeVisible();
    const download = page.waitForEvent("download");
    await row.getByRole("button", { name: "PNG" }).click();
    expect((await download).suggestedFilename()).toMatch(/\.png$/);
    const link = (await api.call<{ items: Link[] }>("GET", `/v1/w/${workspace.id}/entry-links`)).items[0];
    expect(link.opened_conversations).toBe(0);
  });

  test("Automations links to the Entry links page", async ({ page, sandbox }) => {
    await page.goto(`/w/${sandbox.workspace.slug}/automations`);
    await page.getByRole("link", { name: "Entry links" }).click();
    await expect(page.getByRole("heading", { name: "Entry links" })).toBeVisible();
  });
});
