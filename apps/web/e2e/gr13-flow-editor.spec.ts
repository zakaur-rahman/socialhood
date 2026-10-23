import { expect, test } from "./support/fixtures";

/**
 * GR-13 The flow editor. A user builds "comment, ask for an email, branch on a button, send A or B"
 * on a phone-sized screen and on a desktop one, activates it, and it runs on the sandbox: the
 * comment gets the question as its private reply, the email is saved to the contact, a quick reply
 * picks the message. Steps also reorder by dragging, and an activation error jumps to its step.
 */
type Page = import("@playwright/test").Page;
type Locator = import("@playwright/test").Locator;
type Run = { id: string; result: string; conversation_id: string | null };
type FlowBody = {
  definition: { start: string; steps: { id: string; type: string; quick_replies?: { title: string }[] }[] };
};

/** Reload until ``target`` shows: the worker sends each step in turn. */
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
      { timeout: 60_000, intervals: [500] },
    )
    .toBe(true);
}

async function shows(page: Page, text: string) {
  await appears(page, page.getByRole("log", { name: /^Messages with / }).getByText(text));
}

const SIZES = [
  { name: "375 px", width: 375, height: 812 },
  { name: "1280 px", width: 1280, height: 900 },
];

for (const size of SIZES) {
  test.describe(`GR-13 comment, ask for an email, branch on a button, send A or B (${size.name})`, () => {
    test("it is built in the editor and runs on the sandbox", async ({ page, api, sandbox }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
      const { workspace, account } = sandbox;
      const keyword = `gr13${Date.now().toString(36)}`;
      const name = `Flow ${keyword}`;
      const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
        name,
        social_account_id: account.id,
      });
      await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}`, {
        name,
        social_account_id: account.id,
        trigger: "comment_keyword",
        keywords: [keyword],
        match_mode: "word",
        action: "send_message",
        message_text: "Which one would you like?",
        post_scope: "all",
        confirm_first: false,
      });

      await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
      const then = page.getByRole("region", { name: /^Then/ });

      // The automation opens as one message. Adding a step turns it into a flow.
      await then.getByTestId("more-steps").getByRole("button", { name: "Add step" }).click();
      await page.getByRole("menuitem", { name: /^Ask/ }).click();
      const editor = then.getByTestId("flow-editor");
      await expect(editor).toBeVisible();
      await expect(editor.getByTestId("flow-count")).toContainText("2");

      // Ask comes first: write the question, then move it above the message.
      const ask = editor.locator('[data-kind="ask"]');
      await ask.getByRole("textbox", { name: "Question" }).fill("What's your email? We'll send it there.");
      await editor.getByRole("button", { name: "Move step 2 up" }).click();
      await expect(editor.locator("[data-flow-step]").first()).toHaveAttribute("data-kind", "ask");

      // The message is now step 2: give it two quick replies, A and B.
      const message = editor.locator('[data-kind="send"]').first();
      await message.getByRole("textbox", { name: "Message" }).first().fill("Which one would you like?");
      await message.getByRole("button", { name: "Add a quick reply" }).click();
      await message.getByRole("textbox", { name: "Quick reply 1" }).fill("Guide");
      await message.getByRole("button", { name: "Add a quick reply" }).click();
      await message.getByRole("textbox", { name: "Quick reply 2" }).fill("Prices");

      // Each quick reply leads to its own message.
      await page.getByRole("button", { name: "Add step to Quick reply 1 of step 2" }).click();
      await page.getByRole("menuitem", { name: /^Send/ }).click();
      await message
        .getByRole("group", { name: "Quick reply 1 of step 2" })
        .getByRole("textbox", { name: "Message" })
        .fill("Here's the guide.");
      await page.getByRole("button", { name: "Add step to Quick reply 2 of step 2" }).click();
      await page.getByRole("menuitem", { name: /^Send/ }).click();
      await message
        .getByRole("group", { name: "Quick reply 2 of step 2" })
        .getByRole("textbox", { name: "Message" })
        .fill("Prices start at 499.");
      await expect(editor.getByTestId("flow-count")).toContainText("4");
      await expect(page.getByTestId("save-status")).toHaveText("Saved");

      // The Preview walks one branch at a time: pick "Prices" at the button fork.
      const preview = page.getByRole("tabpanel", { name: "Preview" });
      await expect(preview).toContainText("Here's the guide.");
      await preview.getByRole("combobox", { name: "Branch 2" }).selectOption({ label: "Taps Prices" });
      await expect(preview).toContainText("Prices start at 499.");
      await expect(preview).not.toContainText("Here's the guide.");

      await page.getByRole("button", { name: "Activate" }).click();
      await expect(page.getByText("Active. It answers new messages from now on.")).toBeVisible();

      // Nothing overflows sideways at this width.
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(
        true,
      );

      // It runs: the comment gets the question as its private reply.
      const fromId = `e2e_gr13_${size.width}_${Date.now().toString(36)}`;
      const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${draft.id}/runs`);
      await api.inbound(workspace.id, { accountId: account.id, kind: "comment", text: `${keyword} please`, fromId });
      await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 60_000 }).toBe("awaiting_reply");
      const [run] = (await runs()).items;
      await expect.poll(async () => (await runs()).items[0]?.conversation_id, { timeout: 30_000 }).not.toBeNull();
      const conversation = (await runs()).items[0].conversation_id;

      // They answer with their email, the contact keeps it, and the buttons follow.
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Priya@Example.com", fromId });
      await page.goto(`/w/${workspace.slug}/inbox/${conversation}`);
      await shows(page, "Which one would you like?");
      const contacts = await api.call<{ items: { email: string | null }[] }>(
        "GET",
        `/v1/w/${workspace.id}/contacts?q=priya%40example.com`,
      );
      expect(contacts.items.map((c) => c.email)).toContain("priya@example.com");

      // They tap "Prices" (the second quick reply of the message step).
      const flow = await api.call<FlowBody>("GET", `/v1/w/${workspace.id}/automations/${draft.id}/flow`);
      const buttons = flow.definition.steps.find((s) => s.type === "send" && (s.quick_replies?.length ?? 0) > 0);
      expect(buttons?.quick_replies?.map((q) => q.title)).toEqual(["Guide", "Prices"]);
      await api.inbound(workspace.id, {
        accountId: account.id,
        kind: "dm",
        text: "Prices",
        fromId,
        quickReplyPayload: `shf:${run.id}:${buttons?.id}:1`,
      });
      await shows(page, "Prices start at 499.");
    });
  });
}

test.describe("GR-13 reorder and errors", () => {
  /** A saved flow of two messages, not yet activated. */
  async function twoMessages(api: import("./support/api").Api, wid: string, accountId: string, second = "Second") {
    const name = `Order ${Date.now().toString(36)}`;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${wid}/automations`, {
      name,
      social_account_id: accountId,
    });
    await api.call("PUT", `/v1/w/${wid}/automations/${draft.id}`, {
      name,
      social_account_id: accountId,
      trigger: "dm_keyword",
      keywords: [`order${Date.now().toString(36)}`],
      match_mode: "word",
    });
    await api.call("PUT", `/v1/w/${wid}/automations/${draft.id}/flow`, {
      start: "first",
      steps: [
        { type: "send", id: "first", text: "First", next: "second" },
        { type: "send", id: "second", text: second },
      ],
    });
    return draft;
  }

  test("a step is dragged above another and the order is saved", async ({ page, api, sandbox }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const { workspace, account } = sandbox;
    const draft = await twoMessages(api, workspace.id, account.id);
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    const editor = page.getByTestId("flow-editor");
    await expect(editor.locator("[data-flow-step]")).toHaveCount(2);

    const handle = await editor.getByRole("button", { name: "Reorder step 2" }).boundingBox();
    const target = await editor.locator("[data-flow-step]").first().boundingBox();
    if (!handle || !target) throw new Error("the cards are not on screen");
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2, target.y + 4, { steps: 12 });
    await page.mouse.up();

    await expect(page.getByTestId("save-status")).toHaveText("Saved");
    await expect(editor.locator("[data-flow-step]").first()).toHaveAttribute("data-flow-step", "second");
    const saved = await api.call<FlowBody>("GET", `/v1/w/${workspace.id}/automations/${draft.id}/flow`);
    expect(saved.definition.start).toBe("second");
  });

  test("an activation error names its step and the link goes to it", async ({ page, api, sandbox }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const { workspace, account } = sandbox;
    const draft = await twoMessages(api, workspace.id, account.id, "");
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByText("One thing to finish before this can go live.")).toBeVisible();

    const attention = page.getByTestId("flow-attention");
    await expect(attention).toContainText("Write the message to send.");
    await attention.getByRole("button", { name: /^Go to step 2/ }).click();
    await expect(page.getByRole("textbox", { name: "Message" }).nth(1)).toBeFocused();
    await page.getByRole("textbox", { name: "Message" }).nth(1).fill("Second, written");
    await expect(page.getByTestId("save-status")).toHaveText("Saved");
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByText("Active. It answers new messages from now on.")).toBeVisible();
  });

  test("the Free plan stops at five steps", async ({ page, api, sandbox }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const { workspace, account } = sandbox;
    const draft = await twoMessages(api, workspace.id, account.id);
    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    const editor = page.getByTestId("flow-editor");
    for (let added = 0; added < 3; added += 1) {
      await editor.getByRole("button", { name: "Add step", exact: true }).click();
      await page.getByRole("menuitem", { name: /^Delay/ }).click();
    }
    await expect(editor.getByTestId("flow-count")).toContainText("5 of 5");
    await expect(editor.getByText(/Your plan includes 5 steps in a flow/).first()).toBeVisible();
    await expect(editor.getByRole("button", { name: "Add step", exact: true })).toBeDisabled();
  });
});
