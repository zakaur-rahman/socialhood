import { expect, test } from "./support/fixtures";

/**
 * YouTube connect on the sandbox (no Google call): the channel shows on Connections with YouTube's
 * name and no AI controls, and the Add account menu offers nothing about YouTube while the
 * workspace's youtube feature is off. The real connect (Google sign-in, the channel list) needs
 * Google; its steps are covered by the API's integration tests and the web unit tests.
 */
test.describe("YouTube connect", () => {
  test("Connections shows the channel with YouTube's name and no AI controls", async ({ page, youtube }) => {
    const { workspace, account } = youtube;
    await page.goto(`/w/${workspace.slug}/settings/connections`);
    const card = page.getByRole("article", { name: account.display_name ?? "YouTube channel" });
    await expect(card).toBeVisible();
    await expect(card.getByRole("img", { name: "YouTube" })).toBeVisible();
    await expect(card.getByText("YouTube Data API")).toBeVisible();
    await expect(card.getByText("Sandbox", { exact: true })).toBeVisible();
    await expect(card.getByText("AI replies")).toHaveCount(0);
  });

  test("the Add account menu has no YouTube item while the feature is off", async ({ page, youtube }) => {
    await page.goto(`/w/${youtube.workspace.slug}/settings/connections`);
    await page.getByRole("button", { name: "Add account", exact: true }).click();
    await expect(page.getByRole("menuitem", { name: /Facebook/ })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /YouTube/ })).toHaveCount(0);
  });
});
