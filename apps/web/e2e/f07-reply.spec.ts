import type { Page } from "@playwright/test";

import type { Api, SandboxAccount, Workspace } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * F-07 Reply from the inbox. The composer posts with an idempotency key, the bubble shows at once
 * (queued), and the worker's send through the sandbox adapter moves it to Sent, or to Failed with
 * the reason and Retry. The sandbox fails a send whose text carries [sandbox:fail=<code>].
 */
async function openNewConversation(page: Page, api: Api, workspace: Workspace, account: SandboxAccount, fromId: string) {
  const text = unique("Hi! Is the green tote still available?");
  await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text, fromId });
  await page.goto(`/w/${workspace.slug}/inbox`);
  await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: text }).click();
  const log = page.getByRole("log", { name: /^Messages with / });
  await expect(log.getByText(text)).toBeVisible();
  return { log, composer: page.getByRole("textbox", { name: /^Reply to / }) };
}

test.describe("F-07 reply from the inbox", () => {
  test("a typed reply shows at once and moves to Sent", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { log, composer } = await openNewConversation(page, api, workspace, account, "e2e_f07_sent");

    const reply = unique("Yes, it is! Want me to keep one for you?");
    await composer.fill(reply);
    const posted = page.waitForResponse(
      (r) => /\/conversations\/[^/]+\/messages$/.test(r.url()) && r.request().method() === "POST",
    );
    await composer.press("Enter");

    // The optimistic bubble is there before the send finishes; the box is empty for the next one.
    const bubble = log.locator("[data-direction='outbound']").filter({ hasText: reply });
    await expect(bubble).toBeVisible();
    await expect(composer).toHaveValue("");
    const response = await posted;
    expect(response.status()).toBe(202);
    expect(response.request().headers()["idempotency-key"]).toBeTruthy();

    // message.updated: Sent, from the worker's send through the sandbox adapter.
    await expect(bubble.getByRole("img", { name: "Sent" })).toBeVisible();
    await expect(bubble.getByRole("img", { name: "Failed" })).toHaveCount(0);
    await expect(
      page.getByRole("list", { name: "Conversations" }).getByRole("link").first(),
    ).toContainText(`You: ${reply}`);
  });

  test("a send the platform can't confirm shows Failed with the reason, and Retry sends again", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { log, composer } = await openNewConversation(page, api, workspace, account, "e2e_f07_fail");

    const reply = unique("Here you go [sandbox:fail=delivery_unknown]");
    await composer.fill(reply);
    await composer.press("Enter");

    const bubble = log.locator("[data-direction='outbound']").filter({ hasText: reply });
    await expect(bubble.getByRole("img", { name: "Failed" })).toBeVisible();
    const alert = bubble.getByRole("alert");
    await expect(alert).toContainText("We couldn't confirm this was delivered. Check the chat in Instagram before retrying.");

    // Retry: allowed for a failed message, which goes back to queued and is sent again. The
    // sandbox fails it again, so the same bubble (not a second one) ends Failed again.
    const retried = page.waitForResponse((r) => /\/messages\/[^/]+\/retry$/.test(r.url()) && r.request().method() === "POST");
    await alert.getByRole("button", { name: "Retry" }).click();
    const response = await retried;
    expect(response.ok()).toBe(true);
    expect(((await response.json()) as { status: string }).status).toBe("queued");
    await expect(bubble.getByRole("img", { name: "Failed" })).toBeVisible();
    await expect(log.locator("[data-direction='outbound']").filter({ hasText: reply })).toHaveCount(1);
  });

  test("outside the 24-hour window the composer is replaced by the reason", async ({ page, sandbox }) => {
    const { workspace } = sandbox;
    // The sandbox backfills a conversation whose customer last wrote two days ago.
    await page.goto(`/w/${workspace.slug}/inbox`);
    await page
      .getByRole("list", { name: "Conversations" })
      .getByRole("link")
      .filter({ hasText: "What time do you open on Sunday?" })
      .click();
    await expect(page.getByRole("log", { name: /^Messages with / }).getByText("What time do you open on Sunday?")).toBeVisible();

    await expect(page.getByRole("status").filter({ hasText: /You can reply after .+ messages again\. Last message .+ ago\./ })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^Reply to / })).toHaveCount(0);
  });
});
