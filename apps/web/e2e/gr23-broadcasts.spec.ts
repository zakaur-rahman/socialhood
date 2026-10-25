import { expect, test, unique } from "./support/fixtures";

/**
 * GR-23 WhatsApp broadcasts on the sandbox number (the stack runs with BROADCASTS_ENABLED=true).
 *
 * Four customers write to a sandbox WhatsApp number; three agree to marketing messages and one
 * withdraws. The owner (on Pro) composes a broadcast from the saved segment and the approved
 * template, checks the preview (three people, one skipped), and sends it. Each person is then
 * reported as sent, delivered, read and failed (the sandbox injects WhatsApp's statuses), the one
 * who withdrew is skipped, and a STOP reply from one of them revokes their consent.
 */
type Contact = { id: string; name: string; username: string | null };
type Recipient = { contact_name: string; username: string | null; status: string; reason: string | null; stopped: boolean; replied: boolean };
type Consents = { consents: { channel: string; status: string; source: string }[] };

test.describe("GR-23 WhatsApp broadcasts", () => {
  test("a sandbox broadcast to three reports each status, skips the opted-out one, and STOP revokes consent", async ({
    page,
    api,
    workspace,
  }) => {
    const stamp = unique("gr23");
    const number = await api.connectSandbox(workspace.id, "whatsapp");
    await api.setPlan(workspace.id, "pro");

    // Four customers write in; the sandbox makes each a contact with a WhatsApp number.
    const people = [
      { name: `Asha ${stamp}`, wa: `91981${Math.floor(1000000 + Math.random() * 8999999)}`, consent: "granted" },
      { name: `Ben ${stamp}`, wa: `91982${Math.floor(1000000 + Math.random() * 8999999)}`, consent: "granted" },
      { name: `Chitra ${stamp}`, wa: `91983${Math.floor(1000000 + Math.random() * 8999999)}`, consent: "granted" },
      { name: `Dev ${stamp}`, wa: `91984${Math.floor(1000000 + Math.random() * 8999999)}`, consent: "revoked" },
    ];
    for (const person of people) {
      await api.inbound(workspace.id, { accountId: number.id, kind: "dm", text: "Hi", fromId: person.wa, fromUsername: person.name });
    }
    const contacts: Record<string, Contact> = {};
    for (const person of people) {
      await expect
        .poll(
          async () => {
            const found = await api.call<{ items: Contact[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${person.wa}`);
            const contact = found.items.find((c) => c.username === person.wa);
            if (contact) contacts[person.name] = contact;
            return Boolean(contact);
          },
          { timeout: 30_000 },
        )
        .toBe(true);
      await api.call("POST", `/v1/w/${workspace.id}/contacts/${contacts[person.name].id}/consents`, {
        channel: "whatsapp",
        status: person.consent,
        note: "Asked in the shop",
      });
    }
    const segmentName = `Everyone ${stamp}`;
    await api.call("POST", `/v1/w/${workspace.id}/contact-segments`, { name: segmentName, filter: {} });

    // Compose it.
    await page.goto(`/w/${workspace.slug}/broadcasts`);
    await expect(page.getByRole("heading", { name: "Broadcasts", level: 1 })).toBeVisible();
    await page.getByRole("link", { name: /New/ }).click();
    await page.getByLabel("Name").fill(`Diwali sale ${stamp}`);
    await page.getByRole("combobox", { name: "Segment" }).click();
    await page.getByRole("option", { name: segmentName }).click();
    await page.getByRole("combobox", { name: "Template" }).click();
    await page.getByRole("option", { name: /sale_offer/ }).click();
    await page.getByRole("radio", { name: "The same text" }).nth(1).click();
    await page.getByLabel("Variable 2 text").fill("31 October");

    // The preview: three people are sent to; the one who withdrew is skipped, and said so.
    await expect(page.getByTestId("eligible")).toHaveText("3 people", { timeout: 20_000 });
    await expect(page.getByTestId("skipped")).toContainText("1 skipped: asked not to get marketing messages");
    await expect(page.getByTestId("sample")).toContainText("until 31 October");
    await expect(page.getByTestId("broadcast-preview")).toContainText("Meta bills your WhatsApp Business Account directly");

    // Send it, after the confirmation.
    await page.getByRole("button", { name: "Send broadcast" }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("3 people");
    await dialog.getByRole("button", { name: "Send" }).click();
    await page.waitForURL(/\/broadcasts\/[0-9a-f-]{36}$/);
    const broadcastId = page.url().split("/").pop() as string;
    await expect(page.getByRole("heading", { name: `Diwali sale ${stamp}`, level: 1 })).toBeVisible();

    const recipients = () =>
      api
        .call<{ items: Recipient[] }>("GET", `/v1/w/${workspace.id}/broadcasts/${broadcastId}/recipients?limit=100`)
        .then((r) => r.items);
    // By the WhatsApp number: the contact's profile (a made-up name in the sandbox) replaces the
    // name the message carried, a moment after it.
    const named = async (name: string) => {
      const wa = people.find((p) => p.name === name)?.wa;
      return (await recipients()).find((r) => r.username === wa);
    };

    // The name the page shows: the contact's profile name, not the one the message carried.
    const shownName = async (person: (typeof people)[number]) => (await named(person.name))?.contact_name ?? person.name;

    // The worker hands each to the send queue and sends: all three are Sent; the fourth is skipped.
    for (const person of people.slice(0, 3)) {
      await expect.poll(async () => (await named(person.name))?.status, { timeout: 60_000 }).toBe("sent");
    }
    expect((await named(people[3].name))?.status).toBe("skipped");

    // WhatsApp reports back: delivered, read, and a failure with its reason.
    const [asha, ben, chitra, dev] = people;
    await api.inbound(workspace.id, { accountId: number.id, kind: "status", fromId: asha.wa, deliveryStatus: "delivered" });
    await api.inbound(workspace.id, { accountId: number.id, kind: "status", fromId: ben.wa, deliveryStatus: "delivered" });
    await api.inbound(workspace.id, { accountId: number.id, kind: "status", fromId: ben.wa, deliveryStatus: "read" });
    await api.inbound(workspace.id, {
      accountId: number.id,
      kind: "status",
      fromId: chitra.wa,
      deliveryStatus: "failed",
      errorCode: 131026,
      errorText: "Message undeliverable",
    });
    await expect.poll(async () => (await named(asha.name))?.status, { timeout: 30_000 }).toBe("delivered");
    await expect.poll(async () => (await named(ben.name))?.status, { timeout: 30_000 }).toBe("read");
    await expect.poll(async () => (await named(chitra.name))?.status, { timeout: 30_000 }).toBe("failed");

    await page.reload();
    const rows = page.getByTestId("recipient-row");
    await rows.first().waitFor({ timeout: 20_000 });
    await expect(rows).toHaveCount(4);
    await expect(rows.filter({ hasText: await shownName(asha) })).toContainText("Delivered");
    await expect(rows.filter({ hasText: await shownName(ben) })).toContainText("Read");
    await expect(rows.filter({ hasText: await shownName(chitra) })).toContainText("Failed");
    await expect(rows.filter({ hasText: await shownName(chitra) })).toContainText("This person can't receive messages right now.");
    await expect(rows.filter({ hasText: await shownName(dev) })).toContainText("Skipped");
    await expect(rows.filter({ hasText: await shownName(dev) })).toContainText("Asked not to get marketing messages.");
    await expect(page.getByTestId("counts")).toContainText("Failed");

    // Asha replies STOP: her consent is withdrawn, with the message as evidence, and the page says so.
    await api.inbound(workspace.id, { accountId: number.id, kind: "dm", text: "STOP", fromId: asha.wa, fromUsername: asha.name });
    await expect
      .poll(
        async () => {
          const record = await api.call<Consents>("GET", `/v1/w/${workspace.id}/contacts/${contacts[asha.name].id}`);
          const whatsapp = record.consents.find((c) => c.channel === "whatsapp");
          return `${whatsapp?.status}/${whatsapp?.source}`;
        },
        { timeout: 30_000 },
      )
      .toBe("revoked/stop_reply");
    await expect.poll(async () => (await named(asha.name))?.stopped, { timeout: 30_000 }).toBe(true);
    await page.reload();
    await rows.first().waitFor({ timeout: 20_000 });
    await expect(rows.filter({ hasText: await shownName(asha) })).toContainText("Said STOP");

    // The next broadcast to the same segment leaves her out.
    const next = await api.call<{ audience: { eligible: number; opted_out: number } }>(
      "POST",
      `/v1/w/${workspace.id}/broadcasts/preview`,
      {
        social_account_id: number.id,
        segment_id: (
          await api.call<{ items: { id: string; name: string }[] }>("GET", `/v1/w/${workspace.id}/contact-segments`)
        ).items.find((s) => s.name === segmentName)?.id,
        template_name: "welcome_offer",
        template_language: "en",
        variables: [],
      },
    );
    expect(next.audience.eligible).toBe(2);
    expect(next.audience.opted_out).toBe(2);
  });

  test("the Free plan sees what broadcasts are part of, and no composer", async ({ page, api, workspace }) => {
    await api.connectSandbox(workspace.id, "whatsapp");
    await page.goto(`/w/${workspace.slug}/broadcasts`);
    await expect(page.getByText("Broadcasts are part of Pro")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("link", { name: /New/ })).toHaveCount(0);
    const refused = await api
      .call("POST", `/v1/w/${workspace.id}/broadcasts/preview`, {
        social_account_id: "00000000-0000-0000-0000-000000000000",
        segment_id: "00000000-0000-0000-0000-000000000000",
        template_name: "sale_offer",
        template_language: "en",
        variables: [],
      })
      .catch((error: Error) => error.message);
    expect(String(refused)).toContain("404"); // the lookups come before the plan check
  });
});
