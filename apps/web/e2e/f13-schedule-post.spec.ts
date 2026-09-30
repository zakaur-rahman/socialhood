import type { Page } from "@playwright/test";

import type { SandboxAccount, Workspace } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * F-13 Schedule and publish a post. The composer builds a draft (account, a photo from the media
 * library, caption), then either schedules it for later or publishes it now: publish_target
 * creates the sandbox container, poll_container publishes it, and the published post becomes a
 * media item that the Comments page lists. The photo is a seeded library upload
 * (apps/api/scripts/e2e/api.py), so no Cloudinary is involved.
 */
async function composeDraft(page: Page, workspace: Workspace, account: SandboxAccount, caption: string, photo: string) {
  await page.goto(`/w/${workspace.slug}/schedule`);
  await page.getByRole("button", { name: "New post" }).first().click();
  await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule/[0-9a-f-]{36}$`));
  await expect(page.getByRole("heading", { name: "Post", level: 1 })).toBeVisible();

  const handle = `@${account.username}`;
  await page.getByRole("region", { name: "Accounts" }).getByRole("button", { name: handle }).click();

  await page.getByRole("region", { name: "Media" }).getByRole("button", { name: "Media library" }).click();
  const library = page.getByRole("dialog", { name: "Media library" });
  await library.getByRole("list", { name: "Uploads" }).getByRole("button", { name: photo }).click();
  await library.getByRole("button", { name: "Add 1" }).click();
  await expect(library).toBeHidden();
  await expect(page.getByRole("region", { name: "Media" })).toContainText("1 of 10");

  await page.getByRole("region", { name: "Caption" }).getByRole("textbox", { name: "Caption" }).fill(caption);

  // The preview follows live, with the first account's name.
  const preview = page.getByRole("article", { name: "Feed preview" });
  await expect(preview).toContainText(account.username ?? "");
  await expect(preview).toContainText(caption);
  await expect(page.getByRole("region", { name: "Checklist" }).getByRole("link", { name: /^To fix:/ })).toHaveCount(0);
}

function tomorrowUtc(): string {
  return new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

test.describe("F-13 schedule and publish a post", () => {
  test("a draft is scheduled for tomorrow and shows in the schedule", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "autumn-drop.jpg");
    const caption = unique("Autumn drop lands tomorrow #newarrivals");
    await composeDraft(page, workspace, account, caption, "autumn-drop.jpg");

    const when = page.getByRole("region", { name: "When" });
    await expect(when).toContainText("Times are in UTC.");
    await when.getByRole("textbox", { name: "Date" }).fill(tomorrowUtc());
    await when.getByRole("textbox", { name: "Time" }).fill("10:30");

    const scheduled = page.waitForResponse((r) => /\/scheduled-posts\/[^/]+\/schedule$/.test(r.url()) && r.request().method() === "POST");
    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Schedule" }).click();
    const response = await scheduled;
    expect(response.status()).toBe(200);
    expect((response.request().postDataJSON() as { publish_at: string }).publish_at).toBe(`${tomorrowUtc()}T10:30:00.000Z`);
    await expect(page.getByText(/^Scheduled for .*10:30/).first()).toBeVisible();
    await expect(page.getByRole("main").getByText("Scheduled", { exact: true })).toBeVisible();

    // The schedule's list view has it, with its time and account.
    await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Schedule" }).click();
    await page.getByRole("radiogroup", { name: "View" }).getByRole("radio", { name: "List" }).click();
    const listed = page.getByRole("main").getByText(caption).first();
    await expect(listed).toBeVisible();
  });

  test("Publish now publishes through the sandbox, and the post reaches Comments", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.mediaAsset(workspace.id, "studio-tour.jpg");
    const caption = unique("Studio tour, live now");
    await composeDraft(page, workspace, account, caption, "studio-tour.jpg");

    await page.getByRole("region", { name: "Post actions" }).getByRole("button", { name: "Publish now" }).click();
    const confirm = page.getByRole("alertdialog", { name: "Publish now?" });
    await confirm.getByRole("button", { name: "Publish now" }).click();
    await expect(page.getByText("Publishing started.").first()).toBeVisible();

    // Targets settle through the jobs: container created, polled FINISHED, published.
    const banner = page.getByTestId("status-banner");
    await expect(banner).toContainText("Published", { timeout: 60_000 });
    await expect(banner).toContainText(`@${account.username}`);

    // The published post is a media item now, so Comments lists it.
    await page.goto(`/w/${workspace.slug}/comments`);
    await expect(page.getByRole("main").getByText(caption).first()).toBeVisible();
  });
});
