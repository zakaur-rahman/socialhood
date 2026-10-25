import type { Page } from "@playwright/test";

import type { SandboxAccount, Workspace } from "./support/api";
import { expect, test } from "./support/fixtures";
import { pickDay } from "./support/ui";

/**
 * GR-39 Instagram Story scheduling. The composer's Type switch makes the one photo a Story: the
 * caption and first comment go away, the preview becomes a 9:16 phone, the Story publishes
 * through the sandbox (publish_target creates the STORIES container, poll_container publishes
 * it), the published post says when it disappears, and the live stories the automation picker
 * reads include it. The photo is a seeded library upload (apps/api/scripts/e2e/api.py).
 */
async function composeStory(page: Page, workspace: Workspace, account: SandboxAccount, photo: string) {
  await page.goto(`/w/${workspace.slug}/schedule`);
  await page.getByRole("button", { name: "New post" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule/[0-9a-f-]{36}$`));

  await page.getByRole("region", { name: "Accounts" }).getByRole("button", { name: `@${account.username}` }).click();
  await page.getByRole("region", { name: "Media" }).getByRole("button", { name: "Media library" }).click();
  const library = page.getByRole("dialog", { name: "Media library" });
  await library.getByRole("list", { name: "Uploads" }).getByRole("button", { name: photo }).click();
  await library.getByRole("button", { name: "Add 1" }).click();
  await expect(library).toBeHidden();

  // A post has a caption; choosing Story takes it (and the first comment) away.
  await expect(page.getByRole("region", { name: "Caption" })).toBeVisible();
  await page.getByRole("region", { name: "Type" }).getByRole("radio", { name: "Story" }).click();
  await expect(page.getByRole("region", { name: "Caption" })).toHaveCount(0);
  await expect(page.getByTestId("story-hint")).toContainText("disappear after 24 hours");
  await expect(page.getByRole("article", { name: "Story preview" })).toBeVisible();
  await expect(page.getByTestId("post-format")).toHaveText("Story");
}

test.describe("GR-39 Instagram Story scheduling", () => {
  test("a Story publishes through the sandbox and says when it disappears", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "story-sale.jpg");
    await composeStory(page, workspace, account, "story-sale.jpg");
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Publish now" }).click();
    await page.getByRole("alertdialog", { name: "Publish now?" }).getByRole("button", { name: "Publish now" }).click();

    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    await expect(banner).toContainText(`@${account.username}`);
    await expect(page.getByTestId("story-expiry")).toContainText("Disappears");
    // Whether the automation picker lists it among the live stories is checked in the API's
    // integration tests: the sandbox keeps what it published in the worker's memory, which the
    // API process (it answers the picker) can't read.
  });

  test("a scheduled Story shows a Story badge in the schedule", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "story-teaser.jpg");
    await composeStory(page, workspace, account, "story-teaser.jpg");

    const when = page.getByRole("region", { name: "When" });
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    await pickDay(page, when.getByRole("button", { name: "Date" }), tomorrow);
    await when.getByRole("textbox", { name: "Time" }).fill("09:15");

    const scheduled = page.waitForResponse((r) => /\/scheduled-posts\/[^/]+\/schedule$/.test(r.url()) && r.request().method() === "POST");
    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Schedule" }).click();
    expect((await scheduled).status()).toBe(200);

    await page.getByRole("main").getByRole("link", { name: "Schedule", exact: true }).click();
    await page.getByRole("radiogroup", { name: "View" }).getByRole("radio", { name: "List" }).click();
    await page.getByTestId("story-badge").first().waitFor({ timeout: 15_000 });
    await expect(page.getByTestId("story-badge").first()).toBeVisible();
  });
});
