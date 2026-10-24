import { expect, test, unique } from "./support/fixtures";

/**
 * GR-24 follow-ups. A lead moving into a stage starts a sequence, a tag taken off stops it, and the
 * sequence's page shows the numbers the server counted (who entered, why people stopped).
 */
type Person = { id: string; status: string; stop_reason: string | null; stop_text: string | null };
type Conversation = { id: string; contact: { id: string }; last_message_preview: string | null };

test.describe("GR-24 follow-ups", () => {
  test("a stage starts a sequence, a removed tag stops it, and the page shows the numbers", async ({
    page,
    api,
    sandbox,
  }) => {
    test.setTimeout(120_000);
    const { workspace, account } = sandbox;
    const wid = workspace.id;
    const asked = unique("Can I book a slot?");
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: asked, fromId: "e2e_followups_seq" });
    const conversations = await api.call<{ items: Conversation[] }>("GET", `/v1/w/${wid}/conversations`);
    const contact = conversations.items.find((c) => c.last_message_preview === asked)?.contact.id;
    expect(contact).toBeTruthy();

    const needed = await api.call<{ id: string }>("POST", `/v1/w/${wid}/tags`, { name: unique("Subscriber") });
    const created = await api.call<{ id: string; entry: { label: string } }>("POST", `/v1/w/${wid}/sequences`, {
      name: "Qualified follow-up",
      social_account_id: account.id,
      entry: { type: "lead_stage", stage: "qualified" },
      stop: { on_reply: false, removed_tag_ids: [needed.id] },
      steps: [{ delay_seconds: 86_400, text: "Thanks for your interest!" }],
    });
    expect(created.entry.label).toBe("A lead moves into a stage: Qualified");
    await api.call("POST", `/v1/w/${wid}/sequences/${created.id}/activate`);

    await api.call("POST", `/v1/w/${wid}/contacts/${contact}/tags`, { add: [needed.id] });
    await api.call("POST", `/v1/w/${wid}/contacts/${contact}/lead-stage`, { stage: "qualified", note: "Asked to book" });
    const people = () => api.call<{ items: Person[] }>("GET", `/v1/w/${wid}/sequences/${created.id}/enrolments`);
    expect((await people()).items).toHaveLength(1);
    expect((await people()).items[0].status).toBe("active");

    await api.call("POST", `/v1/w/${wid}/contacts/${contact}/tags`, { remove: [needed.id] });
    await expect.poll(async () => (await people()).items[0]?.stop_reason, { timeout: 15_000 }).toBe("tag_removed");

    await page.goto(`/w/${workspace.slug}/sequences/${created.id}`);
    await page.getByRole("heading", { name: "Numbers" }).waitFor({ timeout: 15_000 });
    await expect(page.getByText("A tag they needed was taken off").first()).toBeVisible();
  });
});
