import { expect, test } from "./support/fixtures";

/**
 * GR-03 A flow runs end to end on the sandbox: a keyword DM starts a two-branch flow; a tapped
 * quick reply picks the branch; a question takes the email (a wrong one gets the retry prompt);
 * the branch's message follows. The worker sends each message and moves the run on once it's
 * delivered. A second contact takes the other branch.
 */
const FLOW = {
  start: "hello",
  steps: [
    {
      type: "send",
      id: "hello",
      text: "Hi {first_name|there}! Catalogue or prices?",
      quick_replies: [
        { title: "Catalogue", next: "email" },
        { title: "Prices", next: "prices" },
      ],
    },
    { type: "ask", id: "email", text: "What's your email?", expect: "email", next: "catalogue" },
    { type: "send", id: "catalogue", text: "Here's the catalogue.", buttons: [{ title: "Open", url: "https://example.com/catalogue" }] },
    { type: "send", id: "prices", text: "Prices start at 499." },
  ],
};

type Run = { id: string; result: string; conversation_id: string | null };

type Page = import("@playwright/test").Page;
type Locator = import("@playwright/test").Locator;

/** Reload until ``target`` shows: the worker sends each step in turn, and a reload has to finish
 * loading before it can be found. */
async function appears(page: Page, target: Locator) {
  await expect
    .poll(
      async () => {
        await page.reload();
        return target.first().waitFor({ timeout: 5_000 }).then(
          () => true,
          () => false,
        );
      },
      { timeout: 45_000, intervals: [500] },
    )
    .toBe(true);
}

/** The open conversation shows ``text``. */
async function shows(page: Page, text: string) {
  await appears(page, page.getByRole("log", { name: /^Messages with / }).getByText(text));
}

test.describe("GR-03 a flow with a question and two branches", () => {
  test("each branch runs to its message; the email is saved", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `flow${Date.now().toString(36)}`;
    const automation = await api.flowAutomation(workspace.id, account.id, keyword, FLOW);
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);

    // The keyword DM: its first message goes out with the quick replies, then the run waits.
    const asker = `e2e_gr03_a_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: `${keyword} please`, fromId: asker });
    await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 30_000 }).toBe("awaiting_reply");
    const [run] = (await runs()).items;

    // A tap on "Catalogue" leads to the question.
    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text: "Catalogue",
      fromId: asker,
      quickReplyPayload: `shf:${run.id}:hello:0`,
    });
    await page.goto(`/w/${workspace.slug}/inbox/${run.conversation_id}`);
    await shows(page, "What's your email?");

    // A wrong answer, then the email: the branch's message follows.
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "not sure", fromId: asker });
    await shows(page, "That doesn't look like an email address. Could you send it again?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Priya@Example.com", fromId: asker });
    await shows(page, "Here's the catalogue.");
    const contacts = await api.call<{ items: { email: string | null }[] }>(
      "GET",
      `/v1/w/${workspace.id}/contacts?q=priya%40example.com`,
    );
    expect(contacts.items.map((c) => c.email)).toEqual(["priya@example.com"]);

    // Another contact taps "Prices".
    const browser = `e2e_gr03_b_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: browser });
    await expect.poll(async () => (await runs()).items.filter((r) => r.result === "awaiting_reply").length, { timeout: 30_000 }).toBe(1);
    const waiting = (await runs()).items.find((r) => r.result === "awaiting_reply");
    await api.inbound(workspace.id, {
      accountId: account.id,
      kind: "dm",
      text: "Prices",
      fromId: browser,
      quickReplyPayload: `shf:${waiting?.id}:hello:1`,
    });
    await expect
      .poll(
        async () => {
          const found = await api.call<{ items: { last_message_preview?: string | null }[] }>(
            "GET",
            `/v1/w/${workspace.id}/conversations?limit=50`,
          );
          return found.items.some((c) => (c.last_message_preview ?? "").includes("Prices start at 499."));
        },
        { timeout: 30_000 },
      )
      .toBe(true);
  });
});
