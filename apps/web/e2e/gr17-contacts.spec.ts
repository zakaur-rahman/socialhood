import { readFileSync } from "node:fs";

import { expect, test } from "./support/fixtures";

/**
 * GR-17 The contacts page: filter by "tag = lead-magnet and has email", export exactly those rows,
 * save the filter as a segment, tag the matching contacts in bulk, and open a contact's drawer
 * (full screen on a phone) with its tags, fields and timeline.
 */
type Item = { id: string; name: string; username: string | null };
type Tag = { id: string; name: string };

test.describe("GR-17 contacts", () => {
  test("filter by tag and email, export the right rows, save the segment", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const stamp = Date.now().toString(36);
    const names = ["asha", "bina", "chetan", "divya"].map((n) => `e2e_gr17_${n}_${stamp}`);
    for (const fromUsername of names) {
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi", fromId: fromUsername, fromUsername });
    }
    const find = async (username: string) => {
      let found: Item | undefined;
      await expect
        .poll(
          async () => {
            const list = await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`);
            found = list.items.find((c) => c.username === username);
            return Boolean(found);
          },
          { timeout: 30_000 },
        )
        .toBe(true);
      return found as Item;
    };
    const [asha, bina, chetan, divya] = [await find(names[0]), await find(names[1]), await find(names[2]), await find(names[3])];

    const tag = await api.call<Tag>("POST", `/v1/w/${workspace.id}/tags`, { name: `lead-magnet-${stamp}` });
    for (const c of [asha, bina, chetan]) {
      await api.call("POST", `/v1/w/${workspace.id}/contacts/${c.id}/tags`, { add: [tag.id] });
    }
    for (const c of [asha, chetan, divya]) {
      await api.call("PATCH", `/v1/w/${workspace.id}/contacts/${c.id}`, { email: `${c.username}@example.com` });
    }

    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByRole("button", { name: "Filters" }).click();
    await page.getByRole("checkbox", { name: `Tag ${tag.name}` }).click();
    await page.getByRole("combobox", { name: "Email" }).click();
    await page.getByRole("option", { name: "Has an email" }).click();
    await page.getByRole("button", { name: "Done" }).click();

    const rows = page.getByTestId("contact-row");
    await expect(rows).toHaveCount(2);
    await expect(rows.filter({ hasText: asha.username })).toHaveCount(1);
    await expect(rows.filter({ hasText: chetan.username })).toHaveCount(1);
    await expect(page.getByTestId("contact-count")).toContainText("2 contacts match");

    // Export: the same two rows.
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export CSV" }).click();
    const csv = readFileSync((await (await download).path()) as string, "utf-8");
    const lines = csv.trim().split(/\r?\n/);
    expect(lines).toHaveLength(3); // the header and two contacts
    expect(csv).toContain(`${asha.username}@example.com`);
    expect(csv).toContain(`${chetan.username}@example.com`);
    expect(csv).not.toContain(`${bina.username}@example.com`);
    expect(csv).not.toContain(`${divya.username}`);

    // Save the filters as a segment; it shows as chosen, and clearing then choosing it restores them.
    await page.getByRole("button", { name: "Save as segment" }).click();
    await page.getByLabel("Name").fill(`Lead magnet with email ${stamp}`);
    await page.getByRole("button", { name: "Save", exact: true }).click();
    const segment = page.getByRole("button", { name: `Lead magnet with email ${stamp}`, exact: true });
    await expect(segment).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Clear", exact: true }).click();
    await expect(rows.first()).toBeVisible();
    await segment.click();
    await expect(rows).toHaveCount(2);
  });

  test("tag everyone a filter matches", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const stamp = Date.now().toString(36);
    const names = ["one", "two"].map((n) => `e2e_gr17b_${n}_${stamp}`);
    for (const fromUsername of names) {
      await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi", fromId: fromUsername, fromUsername });
    }
    const tag = await api.call<Tag>("POST", `/v1/w/${workspace.id}/tags`, { name: `bulk-${stamp}` });
    // The username arrives with the contact's profile, a moment after the message: wait for it.
    await expect
      .poll(async () => (await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=e2e_gr17b_`)).items.length, {
        timeout: 30_000,
      })
      .toBe(2);

    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByRole("searchbox", { name: "Search contacts" }).fill(`e2e_gr17b_`);
    const rows = page.getByTestId("contact-row");
    await expect(rows).toHaveCount(2, { timeout: 30_000 });
    await page.getByRole("checkbox", { name: "Select all on this page" }).click();
    await page.getByRole("button", { name: "Tag", exact: true }).click();
    await page.getByRole("combobox", { name: "Tag" }).click();
    await page.getByRole("option", { name: tag.name }).click();
    await page.getByRole("button", { name: "Add tag" }).click();
    await expect(page.getByTestId("tag-chip").filter({ hasText: tag.name })).toHaveCount(2, { timeout: 15_000 });
  });

  test("the drawer edits a contact and shows its timeline, full screen on a phone", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const stamp = Date.now().toString(36);
    const username = `e2e_gr17c_${stamp}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hello", fromId: username, fromUsername: username });
    await api.call("POST", `/v1/w/${workspace.id}/contact-fields`, { key: `city_${stamp.slice(-6)}`, label: "City" });
    await expect
      .poll(async () => (await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`)).items.length, { timeout: 30_000 })
      .toBe(1);

    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByRole("searchbox", { name: "Search contacts" }).fill(username);
    await page.getByTestId("contact-row").first().getByRole("button", { name: /^Open / }).click();

    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    const box = await drawer.boundingBox();
    expect(box?.width).toBeGreaterThanOrEqual(370); // the whole screen
    await drawer.getByLabel("Email").fill("drawer@example.com");
    await drawer.getByLabel("City").fill("Pune");
    await drawer.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("Contact saved")).toBeVisible();

    await expect(drawer.getByRole("list", { name: "Timeline" })).toContainText("Conversation started");
    await drawer.getByRole("button", { name: "Close" }).click();
    await expect(page.getByTestId("contact-row").first()).toContainText("drawer@example.com");
  });
});
