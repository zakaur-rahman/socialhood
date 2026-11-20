import { expect, test, unique } from "./support/fixtures";

/**
 * GR-45 Snooze a conversation: a preset from the menu hides it from the list and the Snoozed view
 * holds it; a short snooze comes back unread by itself (the per-minute wake_snoozed job) with a
 * notification for its assignee; a new message from the customer wakes it early.
 */
type Item = { id: string; snoozed_until: string | null; unread_count: number };
type Overview = { members: { user_id: string; is_you: boolean }[] };
type Notification = { type: string };

test.describe("GR-45 snooze", () => {
  test("snooze from the menu, find it under Snoozed, and unsnooze", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const asked = unique("Can you hold this for me?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: asked, fromId: "e2e_gr45_menu" });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`/w/${workspace.slug}/inbox`);
    const list = page.getByRole("list", { name: "Conversations" });
    const row = list.getByRole("link").filter({ hasText: asked });
    await row.first().waitFor({ timeout: 15_000 });
    await row.first().click();

    await page.getByRole("button", { name: "More actions" }).click();
    await page.getByRole("menuitem", { name: "Snooze…" }).click();
    const dialog = page.getByRole("dialog", { name: "Snooze conversation" });
    await expect(dialog.getByRole("list", { name: "Snooze until" }).getByRole("button")).not.toHaveCount(0);
    await dialog.getByRole("button", { name: /^Tomorrow/ }).click();
    await expect(page.getByText(/^Snoozed until /)).toBeVisible();
    await expect(list.getByRole("link").filter({ hasText: asked })).toHaveCount(0);

    await page.getByRole("radiogroup", { name: "Views" }).getByRole("radio", { name: "Snoozed" }).click();
    const snoozed = list.getByRole("link").filter({ hasText: asked });
    await expect(snoozed).toHaveCount(1);

    // It is in no other view, and the menu offers Unsnooze.
    await snoozed.click();
    await page.getByRole("button", { name: "More actions" }).click();
    await page.getByRole("menuitem", { name: "Unsnooze" }).click();
    await expect(list.getByRole("link").filter({ hasText: asked })).toHaveCount(0);
    await page.getByRole("radiogroup", { name: "Views" }).getByRole("radio", { name: "All", exact: true }).click();
    await expect(list.getByRole("link").filter({ hasText: asked })).toHaveCount(1);
  });

  test("a one-minute snooze comes back unread with a notification, and a new message wakes one early", async ({
    page,
    api,
    sandbox,
  }) => {
    // The snooze ends after 70 s and the job runs on the minute, so waking alone can take ~130 s.
    test.setTimeout(300_000);
    const { workspace, account } = sandbox;
    const wid = workspace.id;
    const username = `e2e_gr45_${Date.now().toString(36)}`;
    const asked = unique("Is it in stock?");
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: asked, fromId: username, fromUsername: username });
    const find = async () =>
      (await api.call<{ items: Item[] }>("GET", `/v1/w/${wid}/conversations?view=all&q=${username}`)).items[0];
    await expect.poll(async () => Boolean(await find()), { timeout: 30_000 }).toBe(true);
    const conversation = (await find()) as Item;

    // Assigned to the owner, so the owner is told when it comes back.
    const me = (await api.call<Overview>("GET", `/v1/w/${wid}/assignment`)).members.find((member) => member.is_you);
    await api.call("PUT", `/v1/w/${wid}/conversations/${conversation.id}/assignee`, { user_id: me?.user_id });
    await api.call("POST", `/v1/w/${wid}/conversations/${conversation.id}/read`);

    const until = new Date(Date.now() + 70_000).toISOString();
    await api.call("PATCH", `/v1/w/${wid}/conversations/${conversation.id}`, { snoozed_until: until });
    const among = async (view: string) =>
      (await api.call<{ items: Item[] }>("GET", `/v1/w/${wid}/conversations?view=${view}&q=${username}`)).items;
    expect(await among("all")).toHaveLength(0);
    expect(await among("snoozed")).toHaveLength(1);

    // The job runs every minute: it is back within about two.
    await expect.poll(async () => (await among("all")).length, { timeout: 180_000, intervals: [5_000] }).toBe(1);
    const woken = (await among("all"))[0];
    expect(woken.snoozed_until).toBeNull();
    expect(woken.unread_count).toBeGreaterThan(0);
    const notes = await api.call<{ items: Notification[] }>("GET", `/v1/w/${wid}/notifications`);
    expect(notes.items.some((item) => item.type === "conversation_snooze_ended")).toBe(true);

    // Snoozed for two days, then the customer writes again.
    await api.call("PATCH", `/v1/w/${wid}/conversations/${conversation.id}`, {
      snoozed_until: new Date(Date.now() + 2 * 86_400_000).toISOString(),
    });
    expect(await among("all")).toHaveLength(0);
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: unique("Hello again?"), fromId: username, fromUsername: username });
    await expect.poll(async () => (await among("all")).length, { timeout: 30_000 }).toBe(1);
    expect(await among("snoozed")).toHaveLength(0);

    await page.goto(`/w/${workspace.slug}/inbox`);
    await expect(page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: "Hello again?" })).toHaveCount(1);
  });
});
