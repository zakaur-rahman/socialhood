import { expect, test } from "./support/fixtures";

/**
 * Polish A (C-135): a name the team saved survives the platform's profile name on the next
 * message, and the account cards use the platforms' own logo colours.
 */
type Item = { id: string; name: string; name_source: string; platform_name: string | null; username: string | null };

test.describe("Polish A names and colours", () => {
  test("a team name survives an inbound message, and going back restores the platform's", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    const username = `e2e_pol_${Date.now().toString(36)}`;
    const send = (fromName: string) =>
      api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "hi", fromId: username, fromUsername: fromName });
    await send(username);
    const find = async (): Promise<Item> => {
      let found: Item | undefined;
      await expect
        .poll(
          async () => {
            const list = await api.call<{ items: Item[] }>("GET", `/v1/w/${workspace.id}/contacts?q=${username}`);
            found = list.items[0];
            return Boolean(found);
          },
          { timeout: 30_000 },
        )
        .toBe(true);
      return found as Item;
    };
    const contact = await find();

    const renamed = await api.call<Item>("PATCH", `/v1/w/${workspace.id}/contacts/${contact.id}`, { name: "Asha (wholesale)" });
    expect(renamed.name).toBe("Asha (wholesale)");
    expect(renamed.name_source).toBe("team");

    // A later message carries the platform's name; the saved name stays.
    await send(`${username}_renamed`);
    await expect
      .poll(async () => (await api.call<Item>("GET", `/v1/w/${workspace.id}/contacts/${contact.id}`)).platform_name, { timeout: 30_000 })
      .not.toBeNull();
    const kept = await api.call<Item>("GET", `/v1/w/${workspace.id}/contacts/${contact.id}`);
    expect(kept.name).toBe("Asha (wholesale)");

    // The drawer says what the platform calls them, and the button goes back to it.
    await page.goto(`/w/${workspace.slug}/contacts`);
    await page.getByTestId("contact-row").filter({ hasText: "Asha (wholesale)" }).first().click();
    const drawer = page.getByRole("dialog");
    await expect(drawer.getByText(/name: /).first()).toBeVisible();
    await drawer.getByRole("button", { name: "Use this name" }).click();
    await expect(drawer.getByRole("button", { name: "Use this name" })).toHaveCount(0);
    const back = await api.call<Item>("GET", `/v1/w/${workspace.id}/contacts/${contact.id}`);
    expect(back.name_source).toBe("platform");
    expect(back.name).toBe(back.platform_name);
  });

  test("the account card badge uses the platform's logo colour", async ({ page, sandbox }) => {
    await page.goto(`/w/${sandbox.workspace.slug}/settings/connections`);
    const badge = page.getByRole("img", { name: "Instagram" }).first();
    await expect(badge).toBeVisible();
    await expect(badge).toHaveClass(/bg-instagram-logo-gradient/);
  });
});
