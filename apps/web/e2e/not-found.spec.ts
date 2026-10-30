import { randomUUID } from "node:crypto";

import { expect, test } from "./support/fixtures";

/**
 * Polish C: an unknown public URL gets a real 404 with the 404 page and its ways out; an unknown
 * URL inside a workspace shows the app 404 in the shell; a deleted resource or one in another
 * workspace shows the same in-page "doesn't exist or was deleted" state with a working back link.
 */
test.describe("not found", () => {
  test("an unknown public URL is a 404 with the page and its links", async ({ page }) => {
    const response = await page.goto("/no-such-page-e2e");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "We can't find that page" })).toBeVisible();
    // C-159: the public 404 shows link cards to the main pages (the illustration is the app 404's).
    await expect(page.getByRole("navigation", { name: "Popular pages" }).getByRole("link")).toHaveCount(6);
    await expect(page.getByTestId("requested-path")).toHaveText("/no-such-page-e2e");
    await expect(page.locator('meta[name="robots"]').first()).toHaveAttribute("content", /noindex/);
    await expect(page.getByRole("link", { name: "See pricing" })).toBeVisible();
    await page.getByRole("link", { name: "See pricing" }).click();
    await expect(page).toHaveURL(/\/pricing$/);
  });

  test("an unknown URL inside a workspace shows the app 404 in the shell", async ({ page, workspace }) => {
    await page.goto(`/w/${workspace.slug}/no-such-page-e2e`);
    await expect(page.getByRole("heading", { name: "We can't find that page" })).toBeVisible();
    await expect(page.getByTestId("requested-path")).toHaveText(`/w/${workspace.slug}/no-such-page-e2e`);
    await page.getByRole("link", { name: "Open Inbox" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/inbox`));
  });

  test("a missing post shows the in-page state and goes back to Schedule", async ({ page, workspace }) => {
    await page.goto(`/w/${workspace.slug}/schedule/${randomUUID()}`);
    await expect(page.getByText("This post doesn't exist or was deleted")).toBeVisible();
    await page.getByRole("link", { name: "Back to Schedule" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/schedule$`));
  });

  test("a missing conversation shows the in-page state and goes back to Inbox", async ({ page, sandbox }) => {
    // A workspace with no connected account shows "Connect an account" instead of the inbox.
    const { workspace } = sandbox;
    await page.goto(`/w/${workspace.slug}/inbox/${randomUUID()}`);
    await expect(page.getByText("This conversation doesn't exist or was deleted")).toBeVisible();
    await page.getByRole("link", { name: "Back to Inbox" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/inbox`));
  });

  test("a contact from another workspace reads the same as a deleted one", async ({ page, api, workspace }) => {
    const other = await api.newWorkspace(`Other ${Date.now().toString(36)}`);
    const account = await api.connectSandbox(other.id);
    const username = `e2e_nf_${Date.now().toString(36)}`;
    await api.inbound(other.id, { accountId: account.id, kind: "dm", text: "hi", fromId: username, fromUsername: username });
    let contactId = "";
    await expect
      .poll(
        async () => {
          const list = await api.call<{ items: { id: string; username: string | null }[] }>(
            "GET",
            `/v1/w/${other.id}/contacts?q=${username}`,
          );
          contactId = list.items.find((c) => c.username === username)?.id ?? "";
          return contactId;
        },
        { timeout: 30_000 },
      )
      .not.toBe("");

    await page.goto(`/w/${workspace.slug}/contacts?contact=${contactId}`);
    const state = page.getByTestId("contact-not-found");
    await expect(state).toContainText("This contact doesn't exist or was deleted");
    await state.getByRole("button", { name: "Back to Contacts" }).click();
    await expect(state).toBeHidden();

    // A contact that never existed gets the same wording.
    await page.goto(`/w/${workspace.slug}/contacts?contact=${randomUUID()}`);
    await expect(page.getByTestId("contact-not-found")).toContainText("This contact doesn't exist or was deleted");
  });
});
