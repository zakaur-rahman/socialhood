import { expect, test } from "./support/fixtures";

/**
 * C-167 API key hardening on the sandbox. A Business member makes a key that expires in 90 days and
 * works only from two address ranges; the list shows both. The key is refused (403) from this
 * machine's address until the allowlist is cleared in the edit dialog, which has no scopes to
 * change. A key made without an expiry shows none.
 */
test.describe("C-167 API key expiry and IP allowlist", () => {
  test("create with an expiry and an allowlist, see them in the list, edit the allowlist", async ({
    page,
    api,
    sandbox,
  }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "max");

    await page.goto(`/w/${workspace.slug}/settings/api-keys`);
    await page.getByRole("button", { name: "Create API key" }).click();
    const dialog = page.getByRole("dialog", { name: "Create an API key" });
    await dialog.getByRole("textbox", { name: "Name" }).fill("Office server");
    await dialog.getByRole("combobox", { name: "Expires" }).click();
    await page.getByRole("option", { name: "90 days" }).click();
    const ips = dialog.getByRole("textbox", { name: "Allowed IP addresses" });
    await ips.fill("203.0.113.0/24");
    await ips.press("Enter");
    await ips.fill("2001:db8::/32");
    await ips.press("Enter");
    await dialog.getByRole("button", { name: "Create key" }).click();

    const shown = page.getByRole("dialog", { name: "Your API key" });
    const key = (await shown.getByTestId("api-key-value").textContent())?.trim() ?? "";
    expect(key).toMatch(/^shk_/);
    await shown.getByRole("button", { name: "Done" }).click();

    const row = page.getByTestId("api-key").filter({ hasText: "Office server" });
    await expect(row).toContainText(/expires \d{1,2} [A-Z][a-z]{2} \d{4}/);
    await expect(row.getByTestId("api-key-ips")).toContainText("203.0.113.0/24, 2001:db8::/32");

    // This machine isn't in the list: refused, not unauthorised.
    const refused = await api.publicCall<{ code: string; detail: string }>(key, "GET", "/contacts");
    expect(refused.status).toBe(403);
    expect(refused.body.detail).toBe("This API key can't be used from this address.");

    // Edit the allowlist: an empty list allows any address.
    await row.getByRole("button", { name: "Edit Office server" }).click();
    const edit = page.getByRole("dialog", { name: "Edit Office server" });
    for (const entry of ["203.0.113.0/24", "2001:db8::/32"]) {
      await edit.getByRole("button", { name: `Remove ${entry}`, exact: true }).click();
    }
    await edit.getByRole("button", { name: "Save" }).click();
    await expect(row.getByTestId("api-key-ips")).toHaveCount(0);
    expect((await api.publicCall(key, "GET", "/contacts")).status).toBe(200);

    // Scopes can't be edited: the dialog has no scope checkboxes.
    await row.getByRole("button", { name: "Edit Office server" }).click();
    await expect(page.getByRole("dialog", { name: "Edit Office server" }).getByRole("checkbox")).toHaveCount(0);
  });

  test("a key made without an expiry shows none", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "max");
    await api.call("POST", `/v1/w/${workspace.id}/api-keys`, { name: "Forever", scopes: ["contacts:read"] });
    await page.goto(`/w/${workspace.slug}/settings/api-keys`);
    const row = page.getByTestId("api-key").filter({ hasText: "Forever" });
    await expect(row).toContainText("never used");
    await expect(row).not.toContainText(/expire/i);
  });
});
