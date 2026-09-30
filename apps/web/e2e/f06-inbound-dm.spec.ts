import { expect, test, unique } from "./support/fixtures";

/**
 * F-06 An inbound DM arrives. Sandbox DMs go through the webhook intake (webhook_events,
 * process_webhook_event), the worker stores them, analyses them and drafts a suggestion, and the
 * open inbox patches its caches from the realtime stream (TR-FE-04), with no reload.
 */
test.describe("F-06 an inbound DM arrives", () => {
  test("a new DM appears live at the top, unread, then opens, is read and is analysed", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await page.goto(`/w/${workspace.slug}/inbox`);
    const list = page.getByRole("list", { name: "Conversations" });
    await expect(page.getByRole("heading", { name: "Inbox", level: 1 })).toBeVisible();

    const text = unique("Do you ship to Pune?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text, fromId: "e2e_f06_pune" });

    // Step 11: the conversation jumps to the top with an unread dot, and the sidebar counts it.
    const row = list.getByRole("link").filter({ hasText: text });
    await expect(row).toBeVisible();
    await expect(list.getByRole("link").first()).toContainText(text);
    await expect(row.getByRole("img", { name: "unread" })).toBeVisible();
    await expect(page.getByRole("link", { name: /^Inbox, \d+ unread$/ })).toBeVisible();

    // Opened: the bubble is there and the conversation is marked read after a second on screen.
    await row.click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/inbox/[0-9a-f-]{36}$`));
    const thread = page.getByRole("region", { name: "Conversation", exact: true });
    // Named from the contact's profile once fetch_contact_profile has run (step 4).
    const log = thread.getByRole("log", { name: /^Messages with / });
    await expect(log.getByText(text)).toBeVisible();
    await expect(row.getByRole("img", { name: "unread" })).toBeHidden();
    await expect(page.getByRole("link", { name: "Inbox", exact: true })).toBeVisible();

    // Step 10: the analysis (analysis.created) and a suggested reply (suggestion.created).
    await expect(log.getByRole("group", { name: "AI analysis" })).toBeVisible();
    await expect(thread.getByRole("region", { name: "Suggested reply" })).toBeVisible();
  });

  test("a DM to an open conversation appears in its thread, and a busier one jumps to the top", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const first = unique("Is the blue scarf back?");
    const second = unique("Can I pay on delivery?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: first, fromId: "e2e_f06_aaaa" });
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: second, fromId: "e2e_f06_bbbb" });

    await page.goto(`/w/${workspace.slug}/inbox`);
    const list = page.getByRole("list", { name: "Conversations" });
    await expect(list.getByRole("link").first()).toContainText(second);

    // The older conversation gets a new message: it moves to the top, with the new preview.
    const followUp = unique("Also, do you gift wrap?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: followUp, fromId: "e2e_f06_aaaa" });
    await expect(list.getByRole("link").first()).toContainText(followUp);
    await expect(list.getByRole("link").filter({ hasText: first })).toHaveCount(0);

    // With it open, the next message appears in the thread without a reload.
    await list.getByRole("link").filter({ hasText: followUp }).click();
    const log = page.getByRole("log", { name: /^Messages with / });
    await expect(log.getByText(first)).toBeVisible();
    await expect(log.getByText(followUp)).toBeVisible();
    const live = unique("Sorry, one more: which sizes?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: live, fromId: "e2e_f06_aaaa" });
    await expect(log.getByText(live)).toBeVisible();
    await expect(list.getByRole("link").first()).toContainText(live);
  });
});
