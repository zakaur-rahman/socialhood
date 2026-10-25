import { expect, test } from "./support/fixtures";

/**
 * GR-09 A DM from an ad (a sandbox referral with an ad id) starts the ad click automation and
 * the conversation shows "From an ad".
 */
type Run = { id: string; result: string; conversation_id: string | null };

test.describe("GR-09 ad clicks", () => {
  test("an ad DM starts the ad automation and the conversation shows its source", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const automation = await api.entryAutomation(workspace.id, account.id, "ad_click", {
      messageText: "Thanks for tapping our ad! Here are the details.",
    });
    const fan = `e2e_gr09_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text: "Is this still on?",
      fromId: fan,
      referralSource: "ad",
      adId: "sandbox_ad_42",
      adTitle: "Diwali hampers",
    });

    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    await expect.poll(async () => (await runs()).items.length, { timeout: 30_000 }).toBe(1);
    const conversationId = (await runs()).items[0].conversation_id;
    expect(conversationId).not.toBeNull();

    await page.goto(`/w/${workspace.slug}/inbox/${conversationId}`);
    // The details panel starts closed on a conversation opened by its address.
    const details = page.getByRole("complementary", { name: "Details" });
    if (!(await details.isVisible())) await page.getByRole("button", { name: "Details" }).click();
    await expect(details.getByTestId("conversation-entry")).toContainText('From an ad: "Diwali hampers"');
  });

  test("an ad click on chosen ads passes over other ads", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const automation = await api.entryAutomation(workspace.id, account.id, "ad_click", {
      messageText: "Only for the spring ad.",
      adIds: ["sandbox_ad_spring"],
    });
    const fan = `e2e_gr09b_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text: "hi",
      fromId: fan,
      referralSource: "ad",
      adId: "sandbox_ad_other",
    });
    await new Promise((resolve) => setTimeout(resolve, 8_000));
    const runs = await api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    expect(runs.items).toHaveLength(0);
  });
});
