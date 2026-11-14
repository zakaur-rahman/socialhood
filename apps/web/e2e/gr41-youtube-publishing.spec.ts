import type { Page } from "@playwright/test";

import type { SandboxAccount, Workspace } from "./support/api";
import { expect, test, unique } from "./support/fixtures";
import { pickDay } from "./support/ui";

/**
 * GR-41 (C-195 Phase 2) YouTube publishing on the sandbox, no Google call:
 * (a) a Short for the YouTube channel alone, through the YouTube dropzone (the direct route: the
 *     browser sends the file to the upload address the API hands out), ends "Scheduled on YouTube"
 *     in the composer and on Schedule;
 * (b) a post to the YouTube channel and an Instagram account goes through the media tray (the
 *     media route) and is scheduled like any other post.
 *
 * SANDBOX DEPENDENCIES, marked "SANDBOX:" below; adjust them to what the API worker ships:
 *  1. The workspace needs the youtube feature (YOUTUBE_WORKSPACES). This assumes the sandbox
 *     channel fixture's workspace has it, or that `api.enableYouTube` exists (see below).
 *  2. For a sandbox channel, POST …/youtube-upload returns an upload_url the browser can PUT to
 *     (our API's fake resumable endpoint, on an origin the CSP's connect-src allows) that answers
 *     200 with {"id": "<video id>"} for the last piece.
 *  3. POST …/youtube-upload/complete on the sandbox marks the target "scheduled" on YouTube.
 */

async function newPost(page: Page, workspace: Workspace) {
  await page.goto(`/w/${workspace.slug}/schedule`);
  await page.getByRole("button", { name: "New post" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule/[0-9a-f-]{36}$`));
}

async function choose(page: Page, account: SandboxAccount) {
  await page
    .getByRole("region", { name: "Accounts" })
    .getByRole("button", { name: new RegExp(`@${account.username ?? account.display_name}`) })
    .click();
}

/** Title, the two required answers and a Short or a video. */
async function fillYouTube(page: Page, title: string, format: "Video" | "Short") {
  const section = page.getByRole("region", { name: "YouTube" });
  await section.getByRole("radio", { name: format }).click();
  await section.getByRole("textbox", { name: "Title" }).fill(title);
  await section.getByRole("group", { name: "Is this video made for kids?" }).getByRole("radio", { name: "No" }).check();
  await section.getByRole("group", { name: /realistic AI-made or altered content/ }).getByRole("radio", { name: "No" }).check();
}

async function pickTomorrow(page: Page, time = "10:30") {
  const when = page.getByRole("region", { name: "When" });
  await pickDay(page, when.getByRole("button", { name: "Date" }), new Date(Date.now() + 86_400_000).toISOString().slice(0, 10));
  await when.getByRole("textbox", { name: "Time" }).fill(time);
}

test.describe("GR-41 YouTube publishing", () => {
  test.beforeEach(async ({ api, youtube }) => {
    // SANDBOX: turn the youtube switch on for this workspace. Replace with what the API offers
    // (a seed endpoint, or a fixture workspace already in YOUTUBE_WORKSPACES).
    const withFeature = api as unknown as { enableYouTube?: (wid: string) => Promise<void> };
    await withFeature.enableYouTube?.(youtube.workspace.id);
  });

  test("a Short for YouTube alone uploads through the dropzone and is scheduled on YouTube", async ({ page, youtube }) => {
    const { workspace, account } = youtube;
    await newPost(page, workspace);
    await choose(page, account);

    // The direct route: the YouTube box instead of the media tray, and Description for the caption.
    await expect(page.getByTestId("youtube-route")).toContainText("straight from your computer to YouTube");
    await expect(page.getByRole("region", { name: "Media" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Description" })).toBeVisible();

    const title = unique("Sourdough at dawn");
    await fillYouTube(page, title, "Short");
    await page.getByRole("region", { name: "Description" }).getByRole("textbox", { name: "Description" }).fill("Shaping the loaves before sunrise.");
    await expect(page.getByRole("article", { name: "YouTube preview" })).toContainText(title);

    await page.getByTestId("youtube-file-input").setInputFiles({ name: "dawn.mp4", mimeType: "video/mp4", buffer: Buffer.alloc(512 * 1024) });
    await expect(page.getByTestId("youtube-file-name")).toHaveText("dawn.mp4");
    await pickTomorrow(page);
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    const started = page.waitForResponse((r) => /\/youtube-upload$/.test(r.url()) && r.request().method() === "POST");
    const completed = page.waitForResponse((r) => /\/youtube-upload\/complete$/.test(r.url()));
    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Schedule" }).click();
    expect((await started).status()).toBe(201); // start_youtube_upload answers 201 Created
    // SANDBOX: the browser PUTs the file to the sandbox upload_url between these two calls.
    expect((await completed).status()).toBe(200);

    await expect(page.getByTestId("youtube-banner")).toContainText("Scheduled on YouTube", { timeout: 30_000 });
    await expect(page.getByTestId("youtube-dropzone")).toContainText("The video is on YouTube");

    // Schedule's list names it "Scheduled on YouTube" with YouTube's mark.
    await page.getByRole("main").getByRole("link", { name: "Schedule", exact: true }).click();
    await page.getByRole("radiogroup", { name: "View" }).getByRole("radio", { name: "List" }).click();
    const row = page.getByRole("main").getByRole("link", { name: /Scheduled on YouTube/ }).first();
    await expect(row).toBeVisible();
    await expect(page.getByRole("main").getByRole("img", { name: "YouTube" }).first()).toBeVisible();
  });

  test("a post to YouTube and Instagram goes through the media tray", async ({ page, api, youtube }) => {
    const { workspace, account } = youtube;
    const instagram = await api.connectSandbox(workspace.id);
    await api.videoAsset(workspace.id, "both-platforms.mp4", 30);
    await newPost(page, workspace);
    await choose(page, instagram);
    await choose(page, account);

    // The media route: the shared tray, no YouTube box, and the composer says why.
    await expect(page.getByTestId("youtube-route")).toContainText("the video is stored once and sent to each");
    await expect(page.getByTestId("youtube-dropzone")).toHaveCount(0);

    await page.getByRole("region", { name: "Media" }).getByRole("button", { name: "Media library" }).click();
    const library = page.getByRole("dialog", { name: "Media library" });
    await library.getByRole("list", { name: "Uploads" }).getByRole("button", { name: "both-platforms.mp4" }).click();
    await library.getByRole("button", { name: "Add 1" }).click();
    await expect(library).toBeHidden();

    await fillYouTube(page, unique("Two places at once"), "Video");
    await page.getByRole("region", { name: "Caption" }).getByRole("textbox", { name: "Caption" }).fill(unique("New bake, everywhere"));
    await expect(page.getByRole("region", { name: "Checklist" })).toContainText("the video is stored once and sent to each");
    await pickTomorrow(page, "11:00");
    await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);

    const scheduled = page.waitForResponse((r) => /\/scheduled-posts\/[^/]+\/schedule$/.test(r.url()) && r.request().method() === "POST");
    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Schedule" }).click();
    expect((await scheduled).status()).toBe(200);
    // No direct upload on this route: the scheduler sends the stored video to each platform.
    await expect(page.getByTestId("youtube-banner")).toHaveCount(0);
    await expect(page.getByRole("main").getByText("Scheduled", { exact: true })).toBeVisible();
  });
});
