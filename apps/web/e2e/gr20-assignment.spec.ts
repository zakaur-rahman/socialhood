import { expect, test, unique } from "./support/fixtures";

/**
 * GR-20 Assignment. With round-robin on, a new customer message is handed to the next available
 * member (here the only member, the owner), who is told; the "Assigned to me" view shows only their
 * conversations; the thread header changes or clears the assignee, the row shows it, and the
 * conversation says so in the thread.
 */
type Notification = { type: string; title: string; link: string | null };
type Overview = { round_robin: boolean; members: { user_id: string; is_you: boolean; available: boolean }[] };

test.describe("GR-20 assignment", () => {
  test("a round-robin assignment notifies the member and the view shows only their conversations", async ({
    page,
    api,
    sandbox,
  }) => {
    const { workspace, account } = sandbox;
    const wid = workspace.id;
    const before = unique("Before round-robin");
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: before, fromId: "e2e_gr20_before" });

    // Owners and admins turn it on in Settings, Members.
    await page.goto(`/w/${workspace.slug}/settings/members`);
    const toggle = page.getByRole("switch", { name: "Round-robin" });
    await expect(toggle).not.toBeChecked();
    await toggle.click();
    await expect(toggle).toBeChecked();

    const asked = unique("Do you ship to Pune?");
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: asked, fromId: "e2e_gr20_after" });

    // The owner is told, in the app.
    await expect
      .poll(async () => {
        const list = await api.call<{ items: Notification[] }>("GET", `/v1/w/${wid}/notifications`);
        return list.items.filter((item) => item.type === "conversation_assigned").length;
      })
      .toBe(1);

    // "Assigned to me" lists the new conversation and not the one from before.
    await page.goto(`/w/${workspace.slug}/inbox?view=mine`);
    const list = page.getByRole("list", { name: "Conversations" });
    await list.getByRole("link").filter({ hasText: asked }).first().waitFor({ timeout: 15_000 });
    await expect(list.getByRole("link").filter({ hasText: before })).toHaveCount(0);
    await expect(list.getByRole("link").filter({ hasText: asked }).getByTestId("row-assignee")).toBeVisible();

    // The thread says who was given it, and the header can clear it.
    await list.getByRole("link").filter({ hasText: asked }).click();
    const log = page.getByRole("log", { name: /^Messages with / });
    await expect(log).toContainText("Assigned to");
    await page.getByTestId("assignee-button").click();
    await page.getByRole("menuitemradio", { name: "Nobody" }).click();
    await expect(page.getByRole("button", { name: "Assign this conversation" }).first()).toBeVisible();
    await expect(log).toContainText("removed");

    // It is no longer in the owner's view after a reload.
    await page.goto(`/w/${workspace.slug}/inbox?view=mine`);
    await expect(page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: asked })).toHaveCount(0);
  });

  test("a member who is away is skipped, and a conversation can still be assigned to them by hand", async ({
    page,
    api,
    sandbox,
  }) => {
    const { workspace, account } = sandbox;
    const wid = workspace.id;
    const me = (await api.call<Overview>("GET", `/v1/w/${wid}/assignment`)).members.find((member) => member.is_you);
    expect(me?.available).toBe(true);
    await api.call("PUT", `/v1/w/${wid}/assignment/settings`, { round_robin: true });
    await api.call("PUT", `/v1/w/${wid}/members/${me?.user_id}/availability`, { available: false });

    const asked = unique("Is anyone there?");
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: asked, fromId: "e2e_gr20_away" });
    await page.goto(`/w/${workspace.slug}/inbox`);
    const row = page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: asked });
    await row.first().waitFor({ timeout: 15_000 });
    await expect(row.getByTestId("row-assignee")).toHaveCount(0);

    // By hand it ignores availability.
    await row.click();
    await page.getByTestId("assignee-button").click();
    await page.getByRole("menuitemradio", { name: /\(you\)/ }).click();
    await expect(row.getByTestId("row-assignee")).toBeVisible();
  });
});
