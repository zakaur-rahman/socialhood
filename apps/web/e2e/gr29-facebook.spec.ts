import { ApiFailure } from "./support/api";
import { expect, test, unique } from "./support/fixtures";

/**
 * GR-29 Facebook Pages on the sandbox (no Meta call): a Messenger message reaches the inbox and is
 * answered from it, a comment on a post gets a public reply and a private message, what Messenger
 * doesn't have is refused with its reason, and a Page shows on Connections, in entry links and in
 * conversation starters with Facebook's name. The real connect (Facebook Login, the Pages list)
 * needs Meta; its steps are covered by the API's integration tests and the web unit tests.
 */
type Run = { id: string; result: string };
type ConversationList = { items: { id: string; platform: string }[] };
type Starters = { items: { id: string; question: string }[]; synced_at: string | null; sync_error: string | null };

test.describe("GR-29 Facebook Pages", () => {
  test("a Messenger message reaches the inbox and is answered from it", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    const text = unique("Hi! Do you deliver on Sundays?");
    const stored = await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text,
      fromId: `e2e_gr29_${Date.now().toString(36)}`,
    });
    expect(stored.stored).toBe(1);

    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: text }).click();
    const log = page.getByRole("log", { name: /^Messages with / });
    await expect(log.getByText(text)).toBeVisible();

    const reply = unique("We do! Orders by Saturday noon.");
    const composer = page.getByRole("textbox", { name: /^Reply to / });
    await composer.fill(reply);
    await composer.press("Enter");
    const bubble = log.locator("[data-direction='outbound']").filter({ hasText: reply });
    await expect(bubble).toBeVisible();
    await expect(bubble.getByRole("img", { name: "Sent" })).toBeVisible();

    const facebookOnly = await api.call<ConversationList>("GET", `/v1/w/${workspace.id}/conversations?platform=facebook`);
    expect(facebookOnly.items.length).toBeGreaterThan(0);
    expect(new Set(facebookOnly.items.map((c) => c.platform))).toEqual(new Set(["facebook"]));
  });

  test("a comment on a post gets a public reply and a private message", async ({ api, facebook }) => {
    const { workspace, account } = facebook;
    const keyword = `price${Date.now().toString(36)}`;
    const automation = await api.commentAutomation(workspace.id, account.id, keyword, {
      messageText: "Here are our prices: https://maple.example/prices",
      publicReplies: ["Sent you a message!"],
    });
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "comment",
      text: `${keyword} please`,
      fromId: `e2e_gr29c_${Date.now().toString(36)}`,
      fromUsername: "Asha Rao",
    });

    await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 45_000 }).toBe("sent");
  });

  test("story triggers are refused on a Page, with the reason", async ({ api, facebook }) => {
    const { workspace, account } = facebook;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: "Story replies",
      social_account_id: account.id,
    });
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}`, {
      name: "Story replies",
      social_account_id: account.id,
      trigger: "story_reply",
      keywords: [],
      match_mode: "word",
      action: "send_message",
      message_text: "Thanks for the reply!",
      post_scope: "all",
    });
    const refused = await api
      .call("POST", `/v1/w/${workspace.id}/automations/${draft.id}/activate`)
      .then(() => null, (error: unknown) => error);
    expect(refused).toBeInstanceOf(ApiFailure);
    expect((refused as ApiFailure).status).toBe(422);
    expect((refused as ApiFailure).body).toContain("Facebook Pages have no story replies or story mentions.");
  });

  test("the editor disables the story triggers for a Page", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name: "Page editor",
      social_account_id: account.id,
    });
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    await expect(page.getByRole("radio", { name: "Facebook comment keyword" })).toBeEnabled();
    await expect(page.getByRole("radio", { name: "Facebook story reply" })).toBeDisabled();
    await expect(page.getByRole("radio", { name: "Facebook story mention" })).toBeDisabled();
  });

  test("Connections shows the Page with Facebook's name", async ({ page, facebook }) => {
    const { workspace } = facebook;
    await page.goto(`/w/${workspace.slug}/settings/connections`);
    const card = page.getByRole("article", { name: "Sandbox page" });
    await expect(card).toBeVisible();
    await expect(card.getByText("Facebook Pages API")).toBeVisible();
    await expect(card.getByText("Sandbox", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Connect Facebook/ })).toBeVisible();
  });

  test("an entry link on a Page opens m.me", async ({ api, facebook }) => {
    const { workspace, account } = facebook;
    const automation = await api.entryAutomation(workspace.id, account.id, "entry_link", {
      messageText: "Welcome from the shop window!",
    });
    const link = await api.entryLink(workspace.id, account.id, { name: "Shop window", automationId: automation.id });
    expect(link.url.startsWith("https://m.me/")).toBe(true);
    expect(link.url.endsWith(`?ref=${link.code}`)).toBe(true);
  });

  test("conversation starters are saved and sent to the Page", async ({ page, api, facebook }) => {
    const { workspace, account } = facebook;
    const path = `/v1/w/${workspace.id}/social-accounts/${account.id}/ice-breakers`;
    const saved = await api.call<Starters>("PUT", path, {
      items: [{ question: "What are your opening hours?", answer_with_ai: true }],
    });
    expect(saved.sync_error).toBeNull();
    expect(saved.synced_at).not.toBeNull();

    await page.goto(`/w/${workspace.slug}/automations/starters`);
    await expect(page.getByText(/On Facebook since/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Send to Facebook again" })).toBeVisible();
  });
});
