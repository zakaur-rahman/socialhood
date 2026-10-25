import type { Page } from "@playwright/test";

import type { SandboxAccount, Workspace } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * GR-30 Facebook publishing on the sandbox (no Meta call): a text post to a Page, one post to an
 * Instagram account and a Page together (a photo from the library), per-platform checklist
 * wording, a Page offered Stories and Reels (C-131), and the best times beside the time picker (a sandbox
 * account has only three synced posts, so it says it needs more history). The real Graph calls
 * are covered by the API's contract tests; Meta behaviour is unverified until a real Page
 * publishes.
 */
async function newPost(page: Page, workspace: Workspace) {
  await page.goto(`/w/${workspace.slug}/schedule`);
  await page.getByRole("button", { name: "New post" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule/[0-9a-f-]{36}$`));
}

async function choose(page: Page, label: string | RegExp) {
  await page.getByRole("region", { name: "Accounts" }).getByRole("button", { name: label }).click();
}

async function publishNow(page: Page) {
  await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Publish now" }).click();
  await page.getByRole("alertdialog", { name: "Publish now?" }).getByRole("button", { name: "Publish now" }).click();
}

test.describe("GR-30 Facebook publishing and best times", () => {
  test("a text post publishes to a Page and links to it on Facebook", async ({ page, facebook }) => {
    const { workspace, account } = facebook;
    await newPost(page, workspace);
    await choose(page, new RegExp(`${account.username ?? account.display_name}`));

    const caption = unique("Open late tonight, come say hi");
    await page.getByRole("region", { name: "Caption" }).getByRole("textbox", { name: "Caption" }).fill(caption);
    const preview = page.getByRole("article", { name: "Facebook preview" });
    await expect(preview).toContainText(caption);
    await expect(page.getByTestId("post-format")).toHaveText("Text");
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    await publishNow(page);
    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    await expect(banner.getByRole("link", { name: /View on Facebook/ })).toHaveAttribute("href", /facebook\.com/);
  });

  test("one post goes to an Instagram account and a Page together", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    const instagram: SandboxAccount = await api.connectSandbox(workspace.id);
    await api.mediaAsset(workspace.id, "both-platforms.jpg");
    await newPost(page, workspace);
    await choose(page, `@${instagram.username}`);
    await choose(page, new RegExp(`${account.username ?? account.display_name}`));

    // Text alone is not enough once an Instagram account is chosen: it needs a photo or video.
    const caption = unique("Fresh bread, both places");
    await page.getByRole("region", { name: "Caption" }).getByRole("textbox", { name: "Caption" }).fill(caption);
    await expect(page.getByRole("region", { name: "Checklist" })).toContainText("Add a photo or video.");

    await page.getByRole("region", { name: "Media" }).getByRole("button", { name: "Media library" }).click();
    const library = page.getByRole("dialog", { name: "Media library" });
    await library.getByRole("list", { name: "Uploads" }).getByRole("button", { name: "both-platforms.jpg" }).click();
    await library.getByRole("button", { name: "Add 1" }).click();
    await expect(library).toBeHidden();
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    // The preview can switch between the two platforms.
    await expect(page.getByRole("combobox", { name: "Account" })).toBeVisible();

    await publishNow(page);
    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    await expect(banner.getByRole("link", { name: /View on Instagram/ })).toBeVisible();
    await expect(banner.getByRole("link", { name: /View on Facebook/ })).toBeVisible();
  });

  test("a Page can be a Story or a Reel (C-131)", async ({ page, facebook }) => {
    const { workspace, account } = facebook;
    await newPost(page, workspace);
    await choose(page, new RegExp(`${account.username ?? account.display_name}`));
    const type = page.getByRole("region", { name: "Type" });
    await expect(type.getByRole("radio", { name: "Story" })).toBeEnabled();
    await expect(type.getByRole("radio", { name: "Reel" })).toBeEnabled();
  });

  test("the time picker says when there is too little history for best times", async ({ page, facebook }) => {
    const { workspace, account } = facebook;
    await newPost(page, workspace);
    await choose(page, new RegExp(`${account.username ?? account.display_name}`));
    await expect(page.getByRole("region", { name: "When" }).getByTestId("best-times-hint")).toContainText("Not enough history for best times yet");

    // The same in the Posting times drawer.
    await page.getByRole("button", { name: "Posting times" }).click();
    const drawer = page.getByRole("dialog", { name: "Posting times" });
    await expect(drawer.getByTestId("best-times-panel")).toContainText("Not enough history for best times yet");
  });
});
