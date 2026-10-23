import { expect, test } from "./support/fixtures";

/**
 * GR-12 A new contact gets the welcome once, on their first DM only. An unmatched DM gets the
 * default reply only while the account's AI mode is Off. The editor offers both triggers.
 */
type Run = { id: string; result: string; conversation_id: string | null };

test.describe("GR-12 welcome and default replies", () => {
  test("a new contact gets the welcome once", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setAiMode(workspace.id, account.id, "off");
    const welcome = await api.fallbackAutomation(workspace.id, account.id, "first_message", "Welcome! Glad you're here.");
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${welcome.id}/runs`);

    const fan = `e2e_gr12_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hello there", fromId: fan });
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);

    // A second DM from the same contact is not a first message: the welcome stays at one run.
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "are you there?", fromId: fan });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    expect((await runs()).items).toHaveLength(1);

    // A different new contact is welcomed too.
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi", fromId: `${fan}_b` });
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(2);
  });

  test("an unmatched DM gets the default reply only while AI is off", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const fallback = await api.fallbackAutomation(workspace.id, account.id, "default_reply", "Thanks, we will reply soon.");
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${fallback.id}/runs`);
    const stamp = Date.now().toString(36);

    await api.setAiMode(workspace.id, account.id, "suggest");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "anything?", fromId: `e2e_gr12_s_${stamp}` });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    expect((await runs()).items).toHaveLength(0);

    await api.setAiMode(workspace.id, account.id, "off");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "anything?", fromId: `e2e_gr12_o_${stamp}` });
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);
  });

  test("a keyword automation wins over the welcome on the first DM", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setAiMode(workspace.id, account.id, "off");
    const welcome = await api.fallbackAutomation(workspace.id, account.id, "first_message", "Welcome!");
    const stamp = Date.now().toString(36);
    const keyword = `price${stamp}`;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: `Keyword ${stamp}`,
      social_account_id: account.id,
    });
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}`, {
      name: `Keyword ${stamp}`,
      social_account_id: account.id,
      trigger: "dm_keyword",
      keywords: [keyword],
      match_mode: "word",
      action: "send_message",
      message_text: "Here is the price list.",
    });
    await api.call("POST", `/v1/w/${workspace.id}/automations/${draft.id}/activate`);

    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: `e2e_gr12_k_${stamp}` });
    const runs = (id: string) => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${id}/runs`);
    await expect.poll(async () => (await runs(draft.id)).items.length, { timeout: 30_000 }).toBe(1);
    expect((await runs(welcome.id)).items).toHaveLength(0);
  });

  test("the editor offers the welcome and default reply triggers", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: "Welcome editor",
      social_account_id: account.id,
    });
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    await page.getByRole("radio", { name: "First message (welcome)" }).click();
    await expect(page.getByText(/the first time they DM this account/)).toBeVisible();
    await page.getByRole("radio", { name: "Any other message (default reply)" }).click();
    await expect(page.getByText(/only while AI replies are Off/)).toBeVisible();
  });
});
