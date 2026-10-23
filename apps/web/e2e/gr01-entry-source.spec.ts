import { expect, test, unique } from "./support/fixtures";

/**
 * GR-01 Where a conversation started. Sandbox referrals and DMs go through the real webhook path
 * (webhook_events, process_webhook_event, ingest): an entry link opened, then a message, starts
 * the conversation "from" that link; a first message from an ad names the ad. The details panel
 * says so.
 */
test.describe("GR-01 where a conversation started", () => {
  test.use({ viewport: { width: 1440, height: 900 } }); // the details panel is open from 1440

  test("an entry link opened, then a message: the details say which link", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const fromId = `e2e_gr01_link_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "referral", fromId, referralSource: "link", ref: "bio" });
    const text = unique("Hi, I came from your bio");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text, fromId });

    await page.goto(`/w/${workspace.slug}/inbox`);
    const row = page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: text });
    await row.click();
    const details = page.getByRole("complementary", { name: "Details" });
    await expect(details.getByTestId("conversation-entry")).toContainText('Entry link "bio"');
  });

  test("a first message from an ad: the details name the ad", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const text = unique("Is the hamper still available?");
    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text,
      fromId: `e2e_gr01_ad_${Date.now().toString(36)}`,
      referralSource: "ad",
      adId: "e2e_ad_1",
      adTitle: "Diwali hampers",
    });

    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: text }).click();
    const details = page.getByRole("complementary", { name: "Details" });
    await expect(details.getByTestId("conversation-entry")).toContainText('Ad "Diwali hampers"');
  });
});
