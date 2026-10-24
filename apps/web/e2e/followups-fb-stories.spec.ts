import type { Page } from "@playwright/test";

import type { SandboxAccount, Workspace } from "./support/api";
import { expect, test } from "./support/fixtures";

/**
 * C-131 Facebook and Stories follow-ups on the sandbox (no Meta call): a long caption for a Page
 * that Instagram would refuse, a video published to a Page as a Reel, a photo Story published to a
 * Page (no address, no live-stories list) and the insights line a published Story shows. Meta's
 * behaviour is unverified until a real Page publishes; the API's unit and contract tests cover the
 * calls. The video is a seeded library upload (apps/api/scripts/e2e/api.py).
 */
async function newPost(page: Page, workspace: Workspace) {
  await page.goto(`/w/${workspace.slug}/schedule`);
  await page.getByRole("button", { name: "New post" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule/[0-9a-f-]{36}$`));
}

async function choose(page: Page, label: string | RegExp) {
  await page.getByRole("region", { name: "Accounts" }).getByRole("button", { name: label }).click();
}

async function addFromLibrary(page: Page, filename: string) {
  await page.getByRole("region", { name: "Media" }).getByRole("button", { name: "Media library" }).click();
  const library = page.getByRole("dialog", { name: "Media library" });
  await library.getByRole("list", { name: "Uploads" }).getByRole("button", { name: filename }).click();
  await library.getByRole("button", { name: "Add 1" }).click();
  await expect(library).toBeHidden();
}

async function publishNow(page: Page) {
  await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Publish now" }).click();
  await page.getByRole("alertdialog", { name: "Publish now?" }).getByRole("button", { name: "Publish now" }).click();
}

const pageLabel = (account: SandboxAccount) => new RegExp(`${account.username ?? account.display_name}`);

test.describe("C-131 Facebook and Stories follow-ups", () => {
  test("a long caption is fine for a Page and refused once Instagram is chosen too", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    await newPost(page, workspace);
    await choose(page, pageLabel(account));
    const caption = "Open late tonight, come say hi. ".repeat(160); // about 5,100 characters
    await page.getByRole("region", { name: "Caption" }).getByRole("textbox", { name: "Caption" }).fill(caption);
    const checklist = page.getByRole("region", { name: "Checklist" });
    await expect(checklist.getByRole("link", { name: /^To fix:/ })).toHaveCount(0);
    await expect(checklist).toContainText("Caption within 63,206 characters");

    const instagram = await api.connectSandbox(workspace.id);
    await choose(page, `@${instagram.username}`);
    await expect(checklist).toContainText("Instagram allows 2,200");
  });

  test("a video is published to a Page as a Reel", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    await api.videoAsset(workspace.id, "page-reel.mp4");
    await newPost(page, workspace);
    await choose(page, pageLabel(account));
    await addFromLibrary(page, "page-reel.mp4");

    const type = page.getByRole("region", { name: "Type" });
    await type.getByRole("radio", { name: "Reel" }).click();
    await expect(page.getByTestId("reel-hint")).toContainText("published to your Facebook Page as a Reel");
    await expect(page.getByTestId("post-format")).toHaveText("Reel");
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    await publishNow(page);
    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    await expect(banner.getByRole("link", { name: /View on Facebook/ })).toBeVisible();
  });

  test("a Reel needs a Facebook Page and one video", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "not-a-video.jpg");
    await newPost(page, workspace);
    await choose(page, `@${account.username}`);
    await addFromLibrary(page, "not-a-video.jpg");
    // An Instagram account alone is not offered the Reel choice: it publishes a video as a Reel already.
    await expect(page.getByRole("region", { name: "Type" }).getByRole("radio", { name: "Reel" })).toHaveCount(0);
  });

  test("a photo Story is published to a Page without an address, and says it has no figures", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    await api.mediaAsset(workspace.id, "page-story.jpg");
    await newPost(page, workspace);
    await choose(page, pageLabel(account));
    await addFromLibrary(page, "page-story.jpg");
    await page.getByRole("region", { name: "Type" }).getByRole("radio", { name: "Story" }).click();
    await expect(page.getByRole("region", { name: "Caption" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    await publishNow(page);
    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    await expect(page.getByTestId("story-expiry")).toContainText("Disappears");
    // Facebook gives no way to read a Page Story back, so there is no link to it.
    await expect(banner.getByRole("link", { name: /View on/ })).toHaveCount(0);
    // Facebook gives no figures for a Page Story, and the line says so.
    await expect(page.getByTestId("story-insights")).toContainText("Facebook doesn't share figures for Page Stories");

    // No read API either way: the live stories the automation picker reads stay empty for a Page.
    const stories = await api.call<{ items: unknown[] }>("GET", `/v1/w/${workspace.id}/stories?account_id=${account.id}`);
    expect(stories.items).toHaveLength(0);
  });
});
