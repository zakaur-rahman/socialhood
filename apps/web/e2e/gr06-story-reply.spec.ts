import { expect, test } from "./support/fixtures";

/**
 * GR-06 A story reply with the keyword gets the automation's DM, recorded as a run. A reply
 * without it, and a story like, get nothing; an automation on a chosen story answers only that
 * story. The editor offers the Story reply trigger.
 */
type Run = { id: string; result: string; matched_keyword: string; conversation_id: string | null };
type Page = import("@playwright/test").Page;
type Locator = import("@playwright/test").Locator;

/** Reload until ``target`` shows: the worker sends the DM after the reply is taken in. */
async function appears(page: Page, target: Locator) {
  await expect
    .poll(
      async () => {
        await page.reload();
        return target.first().waitFor({ timeout: 5_000 }).then(
          () => true,
          () => false,
        );
      },
      { timeout: 45_000, intervals: [500] },
    )
    .toBe(true);
}

test.describe("GR-06 story replies", () => {
  test("a reply with the keyword gets the DM and a run", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `story${Date.now().toString(36)}`;
    const automation = await api.storyAutomation(workspace.id, account.id, "story_reply", {
      keywords: [keyword],
      messageText: "Thanks for replying to our story!",
    });
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    const fan = `e2e_gr06_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "story_reply", text: "where is this?", fromId: fan });
    await api.inbound(workspace.id, { accountId: account.id, kind: "story_like", fromId: fan });
    await api.inbound(workspace.id, { accountId: account.id, kind: "story_reply", text: `${keyword} please`, fromId: fan });

    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);
    const [run] = (await runs()).items;
    expect(run.matched_keyword).toBe(keyword);
    expect(["sent", "queued"]).toContain(run.result);

    await page.goto(`/w/${workspace.slug}/inbox/${run.conversation_id}`);
    await appears(page, page.getByRole("log", { name: /^Messages with / }).getByText("Thanks for replying to our story!"));
  });

  test("a chosen story answers only replies to it", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const stories = await api.call<{ items: { id: string }[] }>("GET", `/v1/w/${workspace.id}/stories?account_id=${account.id}`);
    expect(stories.items.length).toBeGreaterThanOrEqual(2);
    const [chosen, other] = stories.items;
    const automation = await api.storyAutomation(workspace.id, account.id, "story_reply", {
      messageText: "That story was a good one.",
      storyIds: [chosen.id],
    });
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    const fan = `e2e_gr06b_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "story_reply", text: "nice", fromId: fan, storyId: other.id });
    await api.inbound(workspace.id, { accountId: account.id, kind: "story_reply", text: "nice", fromId: `${fan}b`, storyId: chosen.id });

    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);
  });

  test("the editor offers the Story reply trigger", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: "Story editor",
      social_account_id: account.id,
    });
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    await page.getByRole("radio", { name: "Instagram story reply" }).click();
    await expect(page.getByText("On these stories")).toBeVisible();
    await expect(page.getByText("Keywords (optional)")).toBeVisible();
  });
});
