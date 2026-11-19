import type { Page } from "@playwright/test";

import type { Api, SandboxAccount, Workspace } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * GR-42 Reply to a message and react to it, on the sandbox platform. Reply quotes a customer's
 * message (the bubble shows the quote, the sandbox send carries it); a reaction goes to the
 * platform at once and shows under the message. Instagram takes only a heart; a WhatsApp number
 * takes the six of the picker.
 */
async function openConversation(page: Page, api: Api, workspace: Workspace, account: SandboxAccount, fromId: string) {
  const text = unique("Do you ship to Pune?");
  await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text, fromId });
  await page.goto(`/w/${workspace.slug}/inbox`);
  await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: text }).click();
  const log = page.getByRole("log", { name: /^Messages with / });
  const customer = log.locator("[data-direction='inbound']").filter({ hasText: text });
  await expect(customer).toBeVisible();
  return { log, customer, text };
}

const reacted = (page: Page) =>
  page.waitForResponse((r) => /\/messages\/[^/]+\/reaction$/.test(r.url()) && r.request().method() === "PUT");

test.describe("GR-42 reply and react", () => {
  test("Instagram: a reply quotes the customer's message, and a heart reacts to it", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { log, customer, text } = await openConversation(page, api, workspace, account, "e2e_gr42_ig");

    await customer.hover();
    await customer.getByRole("button", { name: "Reply" }).click();
    await expect(page.getByTestId("replying-to")).toContainText(text);
    const composer = page.getByRole("textbox", { name: /^Reply to / });
    await expect(composer).toBeFocused();

    const reply = unique("Yes, in 3 days");
    const posted = page.waitForResponse(
      (r) => /\/conversations\/[^/]+\/messages$/.test(r.url()) && r.request().method() === "POST",
    );
    await composer.fill(reply);
    await composer.press("Enter");
    const response = await posted;
    expect(response.status()).toBe(202);
    expect((response.request().postDataJSON() as { reply_to_message_id: string | null }).reply_to_message_id).toBeTruthy();
    await expect(page.getByTestId("replying-to")).toHaveCount(0);

    const bubble = log.locator("[data-direction='outbound']").filter({ hasText: reply });
    await expect(bubble.getByTestId("reply-quote")).toContainText(text);
    await expect(bubble.getByRole("img", { name: "Sent" })).toBeVisible();
    // The quote survives the worker's message.updated events and a reload.
    await page.reload();
    await expect(log.locator("[data-direction='outbound']").filter({ hasText: reply }).getByTestId("reply-quote")).toContainText(text);

    // Instagram takes a heart only: one toggle, no picker.
    await customer.hover();
    await expect(customer.getByRole("button", { name: "React", exact: true })).toHaveCount(0);
    const heart = reacted(page);
    await customer.getByRole("button", { name: "React with ❤️" }).click();
    expect((await heart).status()).toBe(200);
    await expect(customer.getByRole("img", { name: "Reactions: ❤️" })).toBeVisible();

    // Again removes it.
    const removed = reacted(page);
    await customer.getByRole("button", { name: "Remove your ❤️ reaction" }).click();
    expect((await removed).status()).toBe(200);
    await expect(customer.getByRole("img", { name: /^Reactions:/ })).toHaveCount(0);
  });

  test("WhatsApp: the picker offers six reactions and a thumbs up reacts", async ({ page, api, workspace }) => {
    await api.setPlan(workspace.id, "pro"); // WhatsApp is on Creator and up
    const number = await api.connectSandbox(workspace.id, "whatsapp");
    const { customer } = await openConversation(page, api, workspace, number, "919800000042");

    await customer.hover();
    await customer.getByRole("button", { name: "React", exact: true }).click();
    const picker = page.getByRole("dialog", { name: "Reactions" });
    await expect(picker.getByRole("button", { name: /^React with / })).toHaveCount(6);
    const thumbs = reacted(page);
    await picker.getByRole("button", { name: "React with 👍" }).click();
    expect((await thumbs).status()).toBe(200);
    await expect(customer.getByRole("img", { name: "Reactions: 👍" })).toBeVisible();
  });
});
