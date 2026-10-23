import { expect, test } from "./support/fixtures";

/**
 * GR-14 Data capture and consent. A flow asks for an email, retries a wrong answer, saves the right
 * one to the contact, then asks the marketing consent question; the Yes is recorded on the contact
 * with the messages as proof. The Ask card in the editor carries the same options.
 */
type Run = { id: string; result: string; conversation_id: string | null };
type Contact = {
  id: string;
  email: string | null;
  consents: { channel: string; status: string }[];
};

test.describe("GR-14 data capture and consent", () => {
  test("an email is checked, saved to the contact, and the consent answer is recorded", async ({ api, sandbox }) => {
    const { workspace, account } = sandbox;
    const keyword = `cap${Date.now().toString(36)}`;
    const automation = await api.flowAutomation(workspace.id, account.id, keyword, {
      start: "q",
      steps: [
        {
          type: "ask",
          id: "q",
          text: "What's your email?",
          expect: "email",
          retry_text: "That email doesn't look right. Try once more.",
          tries: 2,
          consent: true,
          confirm_text: "Thanks, you're on the list.",
        },
      ],
    });
    const fromId = `e2e_gr14_${Date.now().toString(36)}`;
    const runs = () => api.call<{ items: Run[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`);
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId });
    await expect.poll(async () => (await runs()).items[0]?.result, { timeout: 60_000 }).toBe("awaiting_reply");
    const [run] = (await runs()).items;

    // A wrong answer is retried; nothing is saved.
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "not an email", fromId });
    const find = async () => {
      const found = await api.call<{ items: Contact[] }>("GET", `/v1/w/${workspace.id}/contacts?q=priya%40example.com`);
      return found.items[0];
    };
    expect(await find()).toBeUndefined();

    // The right one is saved to the contact.
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Priya@Example.com", fromId });
    await expect.poll(async () => (await find())?.email, { timeout: 60_000 }).toBe("priya@example.com");
    const contact = (await find()) as Contact;

    // The consent question follows; a tap on Yes is recorded as marketing consent for Instagram.
    await expect
      .poll(
        async () => {
          await api.inbound(workspace.id, {
            accountId: account.id,
            kind: "dm",
            text: "Yes",
            fromId,
            quickReplyPayload: `shf:${run.id}:q:0`,
          });
          const detail = await api.call<Contact>("GET", `/v1/w/${workspace.id}/contacts/${contact.id}`);
          return detail.consents.map((c) => `${c.channel}:${c.status}`);
        },
        { timeout: 60_000, intervals: [1_000] },
      )
      .toContain("instagram:granted");
  });

  test("the Ask card offers the type, the retry prompt, the tries and the consent option", async ({ page, api, sandbox }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const { workspace, account } = sandbox;
    const name = `Capture ${Date.now().toString(36)}`;
    const draft = await api.call<{ id: string }>("POST", `/v1/w/${workspace.id}/automations`, {
      name,
      social_account_id: account.id,
    });
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}`, {
      name,
      social_account_id: account.id,
      trigger: "dm_keyword",
      keywords: [`card${Date.now().toString(36)}`],
      match_mode: "word",
    });
    await api.call("PUT", `/v1/w/${workspace.id}/automations/${draft.id}/flow`, {
      start: "q",
      steps: [{ type: "ask", id: "q", text: "Your number?", expect: "phone" }],
    });

    await page.goto(`/w/${workspace.slug}/automations/${draft.id}`);
    const ask = page.getByTestId("flow-editor").locator('[data-kind="ask"]');
    await ask.getByRole("combobox", { name: "Tries" }).selectOption("3");
    await ask.getByRole("textbox", { name: "If it doesn't fit, ask again with" }).fill("Send it with the country code.");
    await ask.getByRole("switch", { name: "Ask for marketing consent" }).click();
    await ask.getByRole("textbox", { name: "Consent question" }).fill("Can we send offers here?");
    await expect(page.getByTestId("save-status")).toHaveText("Saved");

    const saved = await api.call<{ definition: { steps: Record<string, unknown>[] } }>(
      "GET",
      `/v1/w/${workspace.id}/automations/${draft.id}/flow`,
    );
    expect(saved.definition.steps[0]).toMatchObject({
      expect: "phone",
      tries: 3,
      retry_text: "Send it with the country code.",
      consent: true,
      consent_text: "Can we send offers here?",
    });
  });
});
