import { expect, test } from "./support/fixtures";

/**
 * GR-05 Activity on the sandbox: an automation whose message can't be sent (the sandbox fails any
 * message containing `[sandbox:fail=<code>]` with that code) shows in Settings, Activity with its
 * reason and the one action, the link to reconnect the account. A DM the automation never gets to
 * answer is not listed (failures only), and the page is for owners and admins.
 */
test.describe("GR-05 activity", () => {
  test("a failed automation shows its reason and the reconnect link", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `act${Date.now().toString(36)}`;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: `Broken ${keyword}`,
      social_account_id: account.id,
    });
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}`, {
      name: `Broken ${keyword}`,
      social_account_id: account.id,
      trigger: "dm_keyword",
      keywords: [keyword],
      match_mode: "word",
      action: "send_message",
      message_text: "Here is the link [sandbox:fail=account_needs_reconnect]",
    });
    await api.call("POST", `/v1/w/${workspace.id}/automations/${draft.id}/activate`);
    const fromId = `e2e_gr05_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId });
    await expect
      .poll(
        async () =>
          (await api.call<{ items: { result: string }[] }>("GET", `/v1/w/${workspace.id}/automations/${draft.id}/runs`))
            .items[0]?.result,
        { timeout: 30_000 },
      )
      .toBe("failed");

    // The API says why and what to do, with no message text in it.
    const feed = await api.call<{ items: { kind: string; automation_id: string | null; action: { href: string } | null }[] }>(
      "GET",
      `/v1/w/${workspace.id}/activity?automation_id=${draft.id}`,
    );
    expect(feed.items[0]).toMatchObject({ kind: "automation_run", action: { href: "/settings/connections" } });

    await page.goto(`/w/${workspace.slug}/settings/activity?automation=${draft.id}`);
    await expect(page.getByRole("heading", { name: "Activity", level: 1 })).toBeVisible();
    const row = page.getByRole("listitem").filter({ hasText: `Broken ${keyword}` }).first();
    await expect(row).toContainText("couldn't reply", { timeout: 30_000 });
    await expect(row).toContainText("Failed");
    await expect(row).toContainText("needs reconnecting");
    const link = row.getByRole("link", { name: "Reconnect Instagram" });
    await expect(link).toHaveAttribute("href", `/w/${workspace.slug}/settings/connections`);
    await link.click();
    await expect(page).toHaveURL(/\/settings\/connections/);
  });
});
