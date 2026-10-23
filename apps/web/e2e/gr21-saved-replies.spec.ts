import { expect, test, unique } from "./support/fixtures";

/**
 * GR-21 Saved replies. Typing /price in the composer lists the reply and Enter inserts it filled in
 * for the customer, with no {braces} left. Owners add replies in Settings. A flow can send one, read
 * when the step runs; a deleted reply fails that step with a plain reason.
 */
type Run = { id: string; result: string; error_message: string | null; conversation_id: string | null };
type Message = { direction: string; text: string | null };

test.describe("GR-21 saved replies", () => {
  test("typing /price in the composer inserts the filled reply", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.savedReply(workspace.id, {
      title: "Prices",
      shortcut: "price",
      body: "Hi {first_name|friend}, prices start at 499. {unknown_field}Anything else?",
    });
    const asked = unique("What are your prices?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: asked, fromId: "e2e_gr21_composer" });
    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: asked }).click();

    const composer = page.getByRole("textbox", { name: /^Reply to / });
    await composer.click();
    await composer.pressSequentially("/pri");
    const option = page.getByRole("option", { name: /\/price/ });
    await expect(option).toBeVisible();
    await composer.press("Enter");

    await expect(composer).toHaveValue(/^Hi .+, prices start at 499\. Anything else\?$/);
    await expect(composer).not.toHaveValue(/[{}]/);
    await expect(page.getByRole("listbox", { name: "Saved replies" })).toHaveCount(0);

    // The filled text sends like any reply.
    await composer.press("Enter");
    const log = page.getByRole("log", { name: /^Messages with / });
    await expect(log.locator("[data-direction='outbound']").filter({ hasText: "prices start at 499." })).toBeVisible();
  });

  test("an owner adds a saved reply in Settings", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.goto(`/w/${workspace.slug}/settings/replies`);
    await expect(page.getByRole("heading", { name: "Saved replies", level: 1 })).toBeVisible();
    await expect(page.getByText("No saved replies yet")).toBeVisible();

    await page.getByRole("button", { name: /New saved reply/ }).first().click();
    await page.getByLabel("Title").fill("Opening hours");
    await page.getByLabel("Shortcut").fill("hours");
    await page.getByLabel("Message", { exact: true }).fill("We are open 9 to 5, {first_name}.");
    await page.getByRole("button", { name: "Add saved reply" }).click();

    const row = page.getByTestId("saved-reply-row");
    await expect(row).toContainText("/hours");
    await expect(row).toContainText("We are open 9 to 5");

    // The same shortcut again is refused, under the field.
    await page.getByRole("button", { name: /New saved reply/ }).first().click();
    await page.getByLabel("Title").fill("Hours again");
    await page.getByLabel("Shortcut").fill("hours");
    await page.getByLabel("Message", { exact: true }).fill("Duplicate");
    await page.getByRole("button", { name: "Add saved reply" }).click();
    await expect(page.getByText("Another saved reply already uses this shortcut.")).toBeVisible();
  });

  test("a flow step sends the saved reply, and a deleted one fails the step", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const reply = await api.savedReply(workspace.id, {
      title: "Prices",
      shortcut: "prices",
      body: "Hi {first_name|there}! Prices start at 499.",
    });
    const keyword = `saved${Date.now().toString(36)}`;
    const flow = {
      start: "prices",
      steps: [{ type: "send", id: "prices", saved_reply_id: reply.id }],
    };
    const automation = await api.flowAutomation(workspace.id, account.id, keyword, flow);
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: "e2e_gr21_flow_a" });
    await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 30_000 }).toBe("sent");
    const [first] = (await runs()).items;
    const sent = await api.call<{ items: Message[] }>(
      "GET",
      `/v1/w/${workspace.id}/conversations/${first.conversation_id}/messages`,
    );
    expect(sent.items.filter((m) => m.direction === "outbound").map((m) => m.text)).toContain(
      "Hi there! Prices start at 499.",
    );

    // Deleted: the next run fails at that step, with a reason a person can act on.
    await api.call("DELETE", `/v1/w/${workspace.id}/saved-replies/${reply.id}`);
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: "e2e_gr21_flow_b" });
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(2);
    const failed = (await runs()).items.find((run) => run.result === "failed");
    expect(failed?.error_message).toContain("saved reply");
  });
});
