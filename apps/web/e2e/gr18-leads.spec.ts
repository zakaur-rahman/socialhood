import { expect, test } from "./support/fixtures";

/**
 * GR-18 Leads: a new contact is a new lead; a member moves it from its card on the board, the
 * drawer shows the history (who and why), and at 375 px the board is one stage at a time.
 */
type Item = { id: string; name: string; username: string | null; lead_stage: string; lead_stage_reason: string | null };

test.describe("GR-18 leads", () => {
  test("move a lead from the board and see it in the history", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const username = `e2e_gr18_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "How much is it?", fromId: username, fromUsername: username });
    let lead: Item | undefined;
    await expect
      .poll(
        async () => {
          const list = await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`);
          lead = list.items.find((c) => c.username === username);
          return Boolean(lead);
        },
        { timeout: 30_000 },
      )
      .toBe(true);
    const found = lead as Item;
    expect(found.lead_stage).toBe("new");

    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`/w/${workspace.slug}/leads`);
    const newColumn = page.getByRole("region", { name: "New leads" });
    const card = newColumn.getByTestId("lead-card").filter({ hasText: found.name });
    await expect(card).toHaveCount(1);

    await card.getByRole("combobox", { name: `Stage for ${found.name}` }).click();
    await page.getByRole("option", { name: "Qualified" }).click();

    const qualified = page.getByRole("region", { name: "Qualified leads" });
    await expect(qualified.getByTestId("lead-card").filter({ hasText: found.name })).toHaveCount(1);
    await expect(newColumn.getByTestId("lead-card").filter({ hasText: found.name })).toHaveCount(0);
    const moved = await api.call<Item>("GET", `/v1/w/${workspace.id}/contacts/${found.id}`);
    expect(moved.lead_stage).toBe("qualified");

    // The drawer: the stage, and the move in the timeline.
    await qualified.getByRole("button", { name: `Open ${found.name}` }).click();
    const drawer = page.getByRole("dialog");
    await expect(drawer.getByTestId("lead-stage")).toHaveText("Qualified");
    await expect(drawer.getByText("Lead stage: Qualified")).toBeVisible();
    await expect(drawer.getByText(/^From New\. By /)).toBeVisible();

    // Move it again from the drawer with a note.
    await drawer.getByLabel("Why? (optional)").fill("Paid by UPI");
    await drawer.getByRole("combobox", { name: "Lead stage" }).click();
    await page.getByRole("option", { name: "Won" }).click();
    await expect(drawer.getByTestId("lead-stage")).toHaveText("Won");
    await expect(drawer.getByText("Lead stage: Won")).toBeVisible();
    await expect(drawer.getByText(/Paid by UPI\.$/)).toBeVisible();
  });

  test("filter the contacts page by stage", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const stamp = Date.now().toString(36);
    const names = ["one", "two"].map((n) => `e2e_gr18b_${n}_${stamp}`);
    for (const fromUsername of names) {
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi", fromId: fromUsername, fromUsername });
    }
    const ids: string[] = [];
    for (const username of names) {
      await expect
        .poll(
          async () => {
            const list = await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`);
            const one = list.items.find((c) => c.username === username);
            if (one) ids[names.indexOf(username)] = one.id;
            return Boolean(one);
          },
          { timeout: 30_000 },
        )
        .toBe(true);
    }
    await api.call("POST", `/v1/w/${workspace.id}/contacts/${ids[0]}/lead-stage`, { stage: "won", note: "Bought" });

    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByRole("button", { name: "Filters" }).click();
    await page.getByRole("checkbox", { name: "Stage Won" }).click();
    await page.getByRole("button", { name: "Done" }).click();
    const rows = page.getByTestId("contact-row");
    await expect(rows.filter({ hasText: names[0] })).toHaveCount(1);
    await expect(rows.filter({ hasText: names[1] })).toHaveCount(0);
    await expect(rows.first().getByTestId("contact-stage")).toHaveText("Won");
  });

  test("at 375 px the board is one stage at a time", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const username = `e2e_gr18c_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi", fromId: username, fromUsername: username });
    let id = "";
    await expect
      .poll(
        async () => {
          const list = await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`);
          id = list.items.find((c) => c.username === username)?.id ?? "";
          return id;
        },
        { timeout: 30_000 },
      )
      .not.toBe("");
    await api.call("POST", `/v1/w/${workspace.id}/contacts/${id}/lead-stage`, { stage: "follow_up" });

    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`/w/${workspace.slug}/leads`);
    await expect(page.getByRole("region", { name: "New leads" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Follow up leads" })).toBeHidden();

    await page.getByRole("group", { name: "Show a stage" }).getByRole("button", { name: /Follow up/ }).click();
    const column = page.getByRole("region", { name: "Follow up leads" });
    await expect(column.getByTestId("lead-card").filter({ hasText: username })).toHaveCount(1);
    await expect(page.getByRole("region", { name: "New leads" })).toBeHidden();
    // No horizontal scroll at 375 px.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
