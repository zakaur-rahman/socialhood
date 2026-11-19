import { expect, test, unique } from "./support/fixtures";

/**
 * GR-43 contact import on the sandbox WhatsApp number. The owner (an admin) imports a CSV from
 * Contacts: the preview lists a new contact, a bad row and, once the consent box is ticked, the
 * people who agreed; the import saves them with their tags and a consent whose source is "import"
 * (its evidence, the file and the row, is checked in the API tests). A second import of the same file changes nothing.
 */
type Contact = { id: string; name: string; phone: string | null; tags: { name: string }[] };
type Record_ = Contact & { consents: { channel: string; status: string; source: string }[] };

test.describe("GR-43 contact import", () => {
  test("previews, imports with the consent box, and importing again changes nothing", async ({ page, api, workspace }) => {
    const stamp = unique("gr43");
    await api.setPlan(workspace.id, "pro"); // WhatsApp isn't on Free
    await api.connectSandbox(workspace.id, "whatsapp");
    const wa = `91981${Math.floor(1000000 + Math.random() * 8999999)}`;
    const file = [
      "Phone,Name,Email,Tags,WhatsApp marketing",
      `+${wa},Asha ${stamp},asha@example.com,vip; march,yes`,
      "not a number,Nobody,,,yes",
    ].join("\n");

    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByRole("button", { name: "Import CSV" }).click();
    const dialog = page.getByRole("dialog", { name: "Import contacts from a CSV file" });
    // The number is known once accounts load; until then the file button is disabled.
    await expect(dialog.getByRole("button", { name: "Choose a CSV file" })).toBeEnabled();
    await dialog.getByTestId("csv-file-input").setInputFiles({ name: "people.csv", mimeType: "text/csv", buffer: Buffer.from(file) });

    // The preview: one new, one left out with its reason; the yes is ignored without the tick.
    await expect(dialog.getByText(/2 rows: 1 new, 0 to update, 0 unchanged, 1 left out\./)).toBeVisible({ timeout: 20_000 });
    await expect(dialog.getByText(/is ignored until you tick the box/)).toBeVisible();
    await expect(dialog.getByText("Enter a phone number with its country code, like +91 98765 43210.")).toBeVisible();

    await dialog.getByRole("checkbox", { name: /These people agreed to get WhatsApp marketing from us/ }).click();
    await expect(dialog.getByText("1 will be marked as agreed to WhatsApp marketing.")).toBeVisible();
    await dialog.getByRole("button", { name: "Import 1 contact" }).click();
    await expect(dialog).toBeHidden();

    const found = await api.call<{ items: Contact[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${wa}`);
    const [asha] = found.items;
    expect(asha.tags.map((t) => t.name).sort()).toEqual(["march", "vip"]);
    const record = await api.call<Record_>("GET", `/v1/w/${workspace.id}/contacts/${asha.id}`);
    const consent = record.consents.find((c) => c.channel === "whatsapp");
    expect(`${consent?.status}/${consent?.source}`).toBe("granted/import");

    // The same file again: nothing is new, nothing changes.
    await page.getByRole("button", { name: "Import CSV" }).click();
    const again = page.getByRole("dialog", { name: "Import contacts from a CSV file" });
    // The number is known once accounts load; until then the file button is disabled.
    await expect(again.getByRole("button", { name: "Choose a CSV file" })).toBeEnabled();
    await again.getByTestId("csv-file-input").setInputFiles({ name: "people.csv", mimeType: "text/csv", buffer: Buffer.from(file) });
    await expect(again.getByText(/2 rows: 0 new, 0 to update, 1 unchanged, 1 left out\./)).toBeVisible({ timeout: 20_000 });
    await expect(again.getByRole("button", { name: "Import" })).toBeDisabled();
  });
});
