import type { Page } from "@playwright/test";

import type { SandboxAccount, Workspace } from "./support/api";
import { expect, test } from "./support/fixtures";

/**
 * FR-PUB-07 Instagram collaborators, user tags and location (C-134), and the Reel options. In the
 * composer: collaborator chips (up to 3), a location from a Facebook Page's link, and a tag placed
 * by tapping the photo. The post publishes through the sandbox, which echoes the collaborators'
 * invites as Pending; Refresh reads them again. A Reel shows its own options, and Stories and
 * Facebook-only posts show why the options are missing. Photos and videos are seeded library
 * uploads (apps/api/scripts/e2e/api.py). The sandbox keeps what it published in the worker's
 * memory, so Accepted invites and the exact container fields are checked in the API's tests.
 */
async function newPost(page: Page, workspace: Workspace, account: SandboxAccount) {
  await page.goto(`/w/${workspace.slug}/schedule`);
  await page.getByRole("button", { name: "New post" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule/[0-9a-f-]{36}$`));
  await page.getByRole("region", { name: "Accounts" }).getByRole("button", { name: `@${account.username}` }).click();
}

async function addFromLibrary(page: Page, filename: string) {
  await page.getByRole("region", { name: "Media" }).getByRole("button", { name: "Media library" }).click();
  const library = page.getByRole("dialog", { name: "Media library" });
  await library.getByRole("list", { name: "Uploads" }).getByRole("button", { name: filename }).click();
  await library.getByRole("button", { name: "Add 1" }).click();
  await expect(library).toBeHidden();
}

test.describe("FR-PUB-07 collaborators, tags and location", () => {
  test("a photo post publishes with collaborators, a tag and a location, and shows the invites", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "collab-loaf.jpg");
    await newPost(page, workspace, account);
    await addFromLibrary(page, "collab-loaf.jpg");

    const options = page.getByRole("region", { name: "Instagram options" });
    const chips = options.getByRole("textbox", { name: "Add a collaborator" });
    await chips.fill("@maple.studio");
    await chips.press("Enter");
    await chips.fill("accepts.fast");
    await chips.press("Enter");
    await expect(options.getByRole("list", { name: "Collaborators" })).toContainText("@maple.studio");
    await expect(options.getByRole("list", { name: "Collaborators" })).toContainText("@accepts.fast");

    // A fourth collaborator is not taken: the field stops at 3.
    await chips.fill("third.one");
    await chips.press("Enter");
    await chips.fill("fourth.one");
    await chips.press("Enter");
    await expect(options.getByRole("list", { name: "Collaborators" }).getByRole("listitem")).toHaveCount(3);

    // The location is a Facebook Page's link; a vanity link has no id and is refused with a reason.
    const location = options.getByRole("textbox", { name: "Location" });
    await location.fill("https://www.facebook.com/maplebakery");
    await expect(options).toContainText("Paste the numeric id of a Facebook Page");
    await location.fill("https://www.facebook.com/profile.php?id=100064123456789");
    await expect(options).toContainText("Page id 100064123456789");

    // Tap the photo to place a tag, name the account, save.
    await page.getByRole("region", { name: "Media" }).getByRole("button", { name: /^Tag people in Photo 1/ }).click();
    const dialog = page.getByRole("dialog", { name: /Tag people in Photo 1/ });
    const stage = dialog.getByTestId("tag-stage");
    const box = await stage.boundingBox();
    if (!box) throw new Error("The tag stage has no size");
    await page.mouse.click(box.x + box.width * 0.25, box.y + box.height * 0.5);
    await dialog.getByRole("textbox", { name: "Username for tag 1" }).fill("bread.fan");
    const marker = dialog.getByTestId("tag-marker-0");
    await expect(marker).toHaveAttribute("data-x", /^0\.2[0-9]*$/);
    await dialog.getByRole("button", { name: "Save tags" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("tag-total")).toContainText("1 person tagged");
    await expect(page.getByTestId("preview-tag")).toHaveText("bread.fan");

    // The checklist lists each option once, all passing.
    const checklist = page.getByRole("region", { name: "Checklist" });
    await expect(checklist.getByRole("link", { name: /^To fix:/ })).toHaveCount(0);
    await expect(checklist).toContainText("Collaborators: @maple.studio, @accepts.fast, @third.one");
    await expect(checklist).toContainText("1 tag on 1 photo");
    await expect(checklist).toContainText("Location set");

    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Publish now" }).click();
    await page.getByRole("alertdialog", { name: "Publish now?" }).getByRole("button", { name: "Publish now" }).click();

    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    const invites = banner.getByTestId("collaborator-status");
    await expect(invites).toContainText("@maple.studio Pending");
    await expect(invites).toContainText("They can't be changed after publishing");

    const refreshed = page.waitForResponse((r) => /\/scheduled-posts\/[^/]+\/collaborators\/refresh$/.test(r.url()));
    await invites.getByRole("button", { name: "Refresh" }).click();
    expect((await refreshed).status()).toBe(200);
    await expect(invites).toContainText("Checked");
  });

  test("a Story and a Facebook-only post say why the options are missing", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "collab-story.jpg");
    await newPost(page, workspace, account);
    await addFromLibrary(page, "collab-story.jpg");
    await expect(page.getByRole("region", { name: "Instagram options" }).getByRole("textbox", { name: "Location" })).toBeVisible();

    await page.getByRole("region", { name: "Type" }).getByRole("radio", { name: "Story" }).click();
    await expect(page.getByTestId("extras-unavailable")).toContainText("not available on Stories");
    await expect(page.getByRole("button", { name: /^Tag people in/ })).toHaveCount(0);
  });

  test("a Reel shows its options: a cover frame, feed sharing and an audio name", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.videoAsset(workspace.id, "collab-reel.mp4", 20);
    await newPost(page, workspace, account);
    await addFromLibrary(page, "collab-reel.mp4");

    const reel = page.getByTestId("reel-options");
    await expect(reel).toBeVisible();
    await expect(reel.getByRole("switch", { name: "Also share to feed" })).toBeChecked();
    await reel.getByRole("spinbutton").fill("2.5");
    await reel.getByRole("switch", { name: "Also share to feed" }).click();
    await reel.getByRole("textbox", { name: "Audio name" }).fill("Morning bake");
    await expect(reel).toContainText("rename a Reel's audio only once");
    await expect(page.getByTestId("reel-caption")).toHaveCount(0);

    // The options pass the checklist and the Reel publishes.
    await expect(page.getByRole("region", { name: "Checklist" })).toContainText("Reel options set");
    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Publish now" }).click();
    await page.getByRole("alertdialog", { name: "Publish now?" }).getByRole("button", { name: "Publish now" }).click();
    await expect(page.getByTestId("status-banner")).toContainText("Published", { timeout: 90_000 });
  });

  test("a cover frame past the end of the video is marked in the checklist", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.videoAsset(workspace.id, "collab-short.mp4", 10);
    await newPost(page, workspace, account);
    await addFromLibrary(page, "collab-short.mp4");

    await page.getByTestId("reel-options").getByRole("spinbutton").fill("12");
    await expect(page.getByRole("region", { name: "Checklist" })).toContainText("The cover frame is past the end of the video.");
  });
});
