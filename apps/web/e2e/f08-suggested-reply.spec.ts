import type { Page } from "@playwright/test";

import type { Api, SandboxAccount, Workspace } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * F-08 Use a suggested reply. After analysis (needs_reply) in Suggest mode, suggest_reply drafts
 * a reply. The e2e worker's fake AI (apps/api/scripts/e2e/worker.py) answers every question with
 * SUGGESTED, and can't answer one that contains [e2e:unknown].
 */
const SUGGESTED = "Thanks for asking! Yes, it's in stock in every colour and ships this week.";

async function conversationWithSuggestion(page: Page, api: Api, workspace: Workspace, account: SandboxAccount, question: string, fromId: string) {
  await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: question, fromId });
  await page.goto(`/w/${workspace.slug}/inbox`);
  await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: question }).click();
  const thread = page.getByRole("region", { name: "Conversation", exact: true });
  return {
    thread,
    log: thread.getByRole("log", { name: /^Messages with / }),
    card: thread.getByRole("region", { name: "Suggested reply" }),
    composer: thread.getByRole("textbox", { name: /^Reply to / }),
  };
}

/** The reply the composer posts: with suggestion_id, the API marks the suggestion sent or edited_sent. */
function replyPosted(page: Page) {
  return page.waitForRequest((r) => /\/conversations\/[^/]+\/messages$/.test(r.url()) && r.method() === "POST");
}

test.describe("F-08 use a suggested reply", () => {
  test("Send posts the suggestion as it is", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { log, card } = await conversationWithSuggestion(page, api, workspace, account, unique("Do you have the linen shirt?"), "e2e_f08_send");

    await expect(card).toContainText(SUGGESTED);
    await expect(card).toContainText("5 drafts left");
    const posted = replyPosted(page);
    await card.getByRole("button", { name: "Send", exact: true }).click();
    const body = (await posted).postDataJSON() as { text: string; suggestion_id?: string };
    expect(body.text).toBe(SUGGESTED);
    expect(body.suggestion_id).toBeTruthy();

    const bubble = log.locator("[data-direction='outbound']").filter({ hasText: SUGGESTED });
    await expect(bubble.getByRole("img", { name: "Sent" })).toBeVisible();
    await expect(card).toBeHidden();
  });

  test("Insert moves the text into the composer; the edited reply goes out", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { thread, log, card, composer } = await conversationWithSuggestion(page, api, workspace, account, unique("Is the red one in stock?"), "e2e_f08_edit");

    await expect(card).toContainText(SUGGESTED);
    await card.getByRole("button", { name: "Insert" }).click();
    await expect(composer).toHaveValue(SUGGESTED);
    await expect(thread.getByText("Editing suggestion")).toBeVisible();
    await expect(card).toBeHidden();

    const edited = `${SUGGESTED} Shall I reserve one?`;
    await composer.fill(edited);
    const posted = replyPosted(page);
    await composer.press("Enter");
    const body = (await posted).postDataJSON() as { text: string; suggestion_id?: string };
    expect(body.text).toBe(edited);
    expect(body.suggestion_id).toBeTruthy();
    const bubble = log.locator("[data-direction='outbound']").filter({ hasText: "Shall I reserve one?" });
    await expect(bubble.getByRole("img", { name: "Sent" })).toBeVisible();
    await expect(thread.getByText("Editing suggestion")).toBeHidden();
    await expect(card).toBeHidden();
  });

  test("Draft again drafts with one draft fewer; Dismiss closes the card", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { card } = await conversationWithSuggestion(page, api, workspace, account, unique("Do you deliver on Sundays?"), "e2e_f08_regen");

    await expect(card).toContainText("5 drafts left");
    const regenerated = page.waitForResponse((r) => /\/conversations\/[^/]+\/suggestions$/.test(r.url()) && r.request().method() === "POST");
    await card.getByRole("button", { name: "Draft again" }).click();
    expect((await regenerated).status()).toBe(202);
    await expect(card).toContainText("4 drafts left");
    await expect(card).toContainText(SUGGESTED);

    await card.getByRole("button", { name: "Dismiss suggestion" }).click();
    await expect(card).toBeHidden();
  });

  test("a question the knowledge doesn't cover says so and offers to add it", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { thread } = await conversationWithSuggestion(page, api, workspace, account, unique("Do you gift wrap? [e2e:unknown]"), "e2e_f08_gift");

    const card = thread.getByRole("region", { name: "Not in your knowledge" });
    await expect(card).toContainText("asked about whether you offer gift wrapping.");
    await expect(card.getByRole("button", { name: "Add to knowledge" })).toBeVisible();
    await card.getByRole("button", { name: "Write reply" }).click();
    await expect(thread.getByRole("textbox", { name: /^Reply to / })).toBeFocused();
  });

  test("a new customer message replaces the pending suggestion", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const { log, card } = await conversationWithSuggestion(page, api, workspace, account, unique("Hello! Quick question [e2e:unknown]"), "e2e_f08_newer");

    await expect(page.getByRole("region", { name: "Not in your knowledge" })).toBeVisible();
    const next = unique("Is the blue scarf back in stock?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: next, fromId: "e2e_f08_newer" });
    await expect(log.getByText(next)).toBeVisible();
    await expect(card).toContainText(SUGGESTED);
    await expect(page.getByRole("region", { name: "Not in your knowledge" })).toHaveCount(0);
  });
});
