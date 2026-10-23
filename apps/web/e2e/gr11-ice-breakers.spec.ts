import { expect, test } from "./support/fixtures";

/**
 * GR-11 Conversation starters: the account's starters are saved and pushed to the sandbox, a tap
 * (a postback with the starter's payload) starts the mapped automation, and a failed push shows
 * its reason. The page is Automations > Conversation starters.
 */
type Starters = {
  items: { id: string; question: string; automation_id: string | null; answer_with_ai: boolean }[];
  synced_at: string | null;
  sync_error: string | null;
};
type Run = { id: string; result: string };

test.describe("GR-11 conversation starters", () => {
  test("a tap starts the mapped automation", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const automation = await api.iceBreakerAutomation(workspace.id, account.id, "Our opening hours are 9 to 6.");
    const path = `/v1/w/${workspace.id}/social-accounts/${account.id}/ice-breakers`;

    const saved = await api.call<Starters>("PUT", path, {
      items: [
        { question: "What are your opening hours?", automation_id: automation.id },
        { question: "Can I talk to someone?", answer_with_ai: true },
      ],
    });
    expect(saved.sync_error).toBeNull();
    expect(saved.synced_at).not.toBeNull();
    const [first] = saved.items;

    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "postback",
      text: first.question,
      postbackPayload: `ib:${first.id}`,
      fromId: `e2e_gr11_${Date.now().toString(36)}`,
    });

    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);
  });

  test("a failed push keeps the list and shows why", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const path = `/v1/w/${workspace.id}/social-accounts/${account.id}/ice-breakers`;
    const saved = await api.call<Starters>("PUT", path, {
      items: [{ question: "Where are you? [sandbox:fail=platform_rejected]", answer_with_ai: true }],
    });
    expect(saved.items).toHaveLength(1);
    expect(saved.sync_error).toBeTruthy();

    await page.goto(`/w/${workspace.slug}/automations/starters`);
    await expect(page.getByText(/Instagram didn't take the list/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Send to Instagram again" })).toBeVisible();
  });

  test("the page saves a starter", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    await page.goto(`/w/${workspace.slug}/automations/starters`);
    await page.getByRole("button", { name: "Add a starter" }).click();
    await page.getByRole("textbox", { name: "Question 1" }).fill("Do you ship abroad?");
    await page.getByRole("combobox", { name: "Answer for question 1" }).click();
    await page.getByRole("option", { name: "Answer with AI" }).click();
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await expect(page.getByText(/On Instagram since/)).toBeVisible();
  });
});
