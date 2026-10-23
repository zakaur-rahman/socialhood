import { expect, test } from "./support/fixtures";

/**
 * GR-07 A story mention gets the automation's thank-you DM, recorded as a run, and shows in
 * Mentions with a link while the story is live.
 */
type Run = { id: string; result: string; conversation_id: string | null };

test.describe("GR-07 story mentions", () => {
  test("a mention triggers the DM and shows in Mentions", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const automation = await api.storyAutomation(workspace.id, account.id, "story_mention", {
      messageText: "Thanks for the mention! Here is a little thank-you.",
    });
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    const fan = `e2e_gr07_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "story_mention", fromId: fan });
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);

    await page.goto(`/w/${workspace.slug}/comments/mentions`);
    const row = page.getByTestId("mention-row").first();
    await expect
      .poll(
        async () => {
          await page.reload();
          return row.waitFor({ timeout: 5_000 }).then(
            () => true,
            () => false,
          );
        },
        { timeout: 45_000, intervals: [500] },
      )
      .toBe(true);
    await expect(row.getByRole("link", { name: /View story/ })).toBeVisible();
    await expect(row.getByRole("link", { name: "Open conversation" })).toBeVisible();
  });

  test("the Comments page links to Mentions", async ({ page, sandbox }) => {
    await page.goto(`/w/${sandbox.workspace.slug}/comments`);
    await page.getByRole("link", { name: "Story mentions" }).click();
    await expect(page.getByRole("heading", { name: "Story mentions" })).toBeVisible();
  });
});
