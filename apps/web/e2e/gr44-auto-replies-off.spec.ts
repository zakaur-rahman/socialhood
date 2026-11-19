import { expect, test } from "./support/fixtures";

/**
 * GR-44 Automatic replies off for one contact: a keyword DM from a contact who has them off starts
 * no automation run, and turning them back on makes the next DM work as before.
 */
type Run = { id: string; result: string };
type Item = { id: string; username: string | null; auto_replies_off: boolean };

test.describe("GR-44 automatic replies off", () => {
  test("a contact with automatic replies off gets no keyword reply", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setAiMode(workspace.id, account.id, "off");
    const stamp = Date.now().toString(36);
    const keyword = `vip${stamp}`;
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
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${draft.id}/runs`);

    const username = `e2e_gr44_${stamp}`;
    const send = () => api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: username, fromUsername: username });
    await send();
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);

    // Turn them off in the contact drawer.
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByRole("searchbox", { name: "Search contacts" }).fill(username);
    const row = page.getByTestId("contact-row");
    await expect(row).toHaveCount(1);
    await row.getByRole("button", { name: /^Open / }).click();
    const drawer = page.getByRole("dialog");
    const toggle = drawer.getByRole("switch", { name: "Automatic replies" });
    await expect(toggle).toBeChecked();
    await toggle.click();
    await expect(toggle).not.toBeChecked();
    const contact = async () =>
      (await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`)).items.find((c) => c.username === username);
    await expect.poll(async () => (await contact())?.auto_replies_off).toBe(true);

    // The next keyword DM starts nothing.
    await send();
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    expect((await runs()).items).toHaveLength(1);

    // On again: the keyword works as before.
    await toggle.click();
    await expect(toggle).toBeChecked();
    await expect.poll(async () => (await contact())?.auto_replies_off).toBe(false);
    await send();
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(2);
  });
});
