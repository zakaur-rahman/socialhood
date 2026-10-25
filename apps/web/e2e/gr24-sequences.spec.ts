import { expect, test, unique } from "./support/fixtures";

/**
 * GR-24 Sequences. A sequence is timed steps after an entry event. Here a tag starts it, the first
 * two steps wait no time (so the worker's minutely sweep sends them) and the third waits a day; when
 * the contact replies after the second, the sequence stops and the page says why. The editor makes a
 * draft from the form. (The three-day schedule itself, with a WhatsApp template and consent, is in
 * the API's integration tests, which can move the clock.)
 */
type Person = {
  id: string;
  status: string;
  stop_reason: string | null;
  stop_text: string | null;
  next_step: number | null;
  last_run: { position: number; status: string } | null;
};
type Conversation = { id: string; contact: { id: string }; last_message_preview: string | null };

test.describe("GR-24 sequences", () => {
  test("a tag starts a sequence, two steps go out, and a reply stops it", async ({ page, api, sandbox }) => {
    test.setTimeout(240_000);
    const { workspace, account } = sandbox;
    const wid = workspace.id;
    const asked = unique("Do you have it in blue?");
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: asked, fromId: "e2e_gr24_reply" });
    const contactOf = async () =>
      (await api.call<{ items: Conversation[] }>("GET", `/v1/w/${wid}/conversations`)).items.find((c) => c.last_message_preview === asked)?.contact.id;
    await expect.poll(contactOf, { timeout: 30_000 }).toBeTruthy();
    const contact = await contactOf();

    const tag = await api.call<{ id: string }>("POST", `/v1/w/${wid}/tags`, { name: unique("Follow up") });
    const created = await api.call<{ id: string }>("POST", `/v1/w/${wid}/sequences`, {
      name: "Follow up",
      social_account_id: account.id,
      entry: { type: "tagged", tag_id: tag.id },
      steps: [
        { delay_seconds: 0, text: "Thanks for asking, {first_name}!" },
        { delay_seconds: 0, delay_from: "previous", text: "Anything else I can help with?" },
        { delay_seconds: 86_400, delay_from: "previous", text: "Still thinking it over?" },
      ],
    });
    await api.call("POST", `/v1/w/${wid}/sequences/${created.id}/activate`);

    await api.call("POST", `/v1/w/${wid}/contacts/${contact}/tags`, { add: [tag.id] });
    const people = () => api.call<{ items: Person[] }>("GET", `/v1/w/${wid}/sequences/${created.id}/enrolments`);
    expect((await people()).items).toHaveLength(1);

    // The worker's sweep runs every minute: step 1, then step 2 a minute later.
    await expect
      .poll(async () => (await people()).items[0]?.last_run?.position, { timeout: 180_000, intervals: [5_000] })
      .toBe(2);

    // The page shows where they are.
    await page.goto(`/w/${workspace.slug}/sequences/${created.id}`);
    const row = page.getByTestId("person-row").first();
    await row.waitFor({ timeout: 15_000 });
    await expect(row).toContainText("On step 3 of 3");
    await expect(row).toContainText("Step 2: sent");

    // They reply: the sequence stops for them.
    await api.inbound(wid, { accountId: account.id, kind: "dm", text: "Yes please", fromId: "e2e_gr24_reply" });
    await expect.poll(async () => (await people()).items[0]?.stop_reason, { timeout: 30_000 }).toBe("reply");
    await page.reload();
    const stopped = page.getByTestId("person-row").first();
    await stopped.waitFor({ timeout: 15_000 });
    await expect(stopped).toContainText("They replied");
    await expect(stopped.getByText("Stopped")).toBeVisible();

    // The third step was never sent.
    const thread = (await api.call<{ items: Conversation[] }>("GET", `/v1/w/${wid}/conversations`)).items.find(
      (c) => c.contact.id === contact,
    );
    const messages = await api.call<{ items: { text: string | null }[] }>(
      "GET",
      `/v1/w/${wid}/conversations/${thread?.id}/messages`,
    );
    expect(messages.items.some((m) => m.text === "Anything else I can help with?")).toBe(true);
    expect(messages.items.some((m) => m.text === "Still thinking it over?")).toBe(false);
  });

  test("the editor saves a draft from the form", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    const name = unique("Welcome");
    const tag = unique("Lead");
    await api.call("POST", `/v1/w/${workspace.id}/tags`, { name: tag });
    await page.goto(`/w/${workspace.slug}/sequences/new`);
    await expect(page.getByRole("heading", { name: "New sequence", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save as draft" })).toBeDisabled();

    await page.getByLabel("Name", { exact: true }).fill(name);
    await page.getByRole("combobox", { name: "Tag" }).click();
    await page.getByRole("option", { name: tag }).click();
    await page.getByLabel("Message").first().fill("Hi {first_name}, thanks for getting in touch.");
    await expect(page.getByTestId("preview-step").first()).toContainText("Hi Priya, thanks for getting in touch.");
    await page.getByRole("button", { name: "Save as draft" }).click();

    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/sequences/[0-9a-f-]+$`));
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
    await expect(page.getByText("Draft", { exact: true }).first()).toBeVisible();

    // The list shows it with what starts it.
    await page.goto(`/w/${workspace.slug}/sequences`);
    const row = page.getByTestId("sequence-row").filter({ hasText: name });
    await expect(row).toContainText(`Starts when: A tag is added: ${tag}`);
    await expect(row).toContainText("1 step");
  });
});
