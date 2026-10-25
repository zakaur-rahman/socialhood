import { expect, test } from "./support/fixtures";

/**
 * GR-25 Public API and API keys on the sandbox. Done when a key with read scope lists contacts and
 * gets 403 on a write. A Free workspace is told the API is part of Pro; on Pro a member makes a key
 * in Settings > Integrations (shown once), uses it, sees when it was last used, and revokes it.
 * The reference page renders from the API's own OpenAPI document.
 */
type ContactList = { items: { id: string }[] };

test.describe("GR-25 public API and API keys", () => {
  test("a Free workspace is told the public API is part of Pro", async ({ page, api, workspace }) => {
    await page.goto(`/w/${workspace.slug}/settings/integrations`);
    await expect(page.getByRole("heading", { name: "Integrations", level: 1 })).toBeVisible();
    await expect(page.getByText("The public API, API keys and Zapier are part of Pro.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create API key" })).toHaveCount(0);

    const refused = await api
      .call("POST", `/v1/w/${workspace.id}/api-keys`, { name: "Zapier", scopes: ["contacts:read"] })
      .then(() => null)
      .catch((error: { status: number; body: string }) => error);
    expect(refused?.status).toBe(402);
    expect(JSON.parse(refused?.body ?? "{}")).toMatchObject({ code: "entitlement_required", entitlement: "public_api" });
  });

  test("a read key lists contacts and is refused a write; revoking stops it", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const fromId = `e2e_gr25_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Do you ship to Pune?", fromId });

    // Make the key in the UI: it is shown once.
    await page.goto(`/w/${workspace.slug}/settings/integrations`);
    await page.getByRole("button", { name: "Create API key" }).click();
    const dialog = page.getByRole("dialog", { name: "Create an API key" });
    await dialog.getByRole("textbox", { name: "Name" }).fill("Sheets sync");
    await expect(dialog.getByRole("checkbox", { name: /contacts:read/ })).toBeChecked();
    await dialog.getByRole("button", { name: "Create key" }).click();
    const shown = page.getByRole("dialog", { name: "Your API key" });
    const key = (await shown.getByTestId("api-key-value").textContent())?.trim() ?? "";
    expect(key).toMatch(/^shk_/);
    await shown.getByRole("button", { name: "Done" }).click();
    await expect(page.getByText(key)).toHaveCount(0); // not shown again

    const row = page.getByTestId("api-key").filter({ hasText: "Sheets sync" });
    await expect(row).toContainText(key.slice(0, 12));
    await expect(row).toContainText("contacts:read");
    await expect(row).toContainText("never used");

    // The done-when: read works, a write is 403.
    await expect
      .poll(async () => ((await api.publicCall<ContactList>(key, "GET", "/contacts")).body.items ?? []).length, {
        timeout: 30_000,
      })
      .toBeGreaterThan(0);
    const contacts = await api.publicCall<ContactList>(key, "GET", "/contacts");
    expect(contacts.status).toBe(200);
    const write = await api.publicCall<{ code: string; detail: string }>(
      key,
      "PATCH",
      `/contacts/${contacts.body.items[0].id}`,
      { email: "priya@example.com" },
    );
    expect(write.status).toBe(403);
    expect(write.body.code).toBe("forbidden");
    expect(write.body.detail).toContain("contacts:write");
    expect((await api.publicCall(key, "GET", "/tags")).status).toBe(403); // no tags:read either

    // It shows as used, then revoking stops it at once.
    await page.reload();
    await expect(page.getByTestId("api-key").filter({ hasText: "Sheets sync" })).toContainText("last used", {
      timeout: 15_000,
    });
    await page.getByTestId("api-key").filter({ hasText: "Sheets sync" }).getByRole("button", { name: "Revoke" }).click();
    await page.getByRole("alertdialog", { name: "Revoke Sheets sync?" }).getByRole("button", { name: "Revoke key" }).click();
    await expect(page.getByTestId("api-key").filter({ hasText: "Sheets sync" })).toContainText("Revoked");
    expect((await api.publicCall(key, "GET", "/contacts")).status).toBe(401);
  });

  test("the public API reference renders from the API's OpenAPI document", async ({ page }) => {
    await page.goto("/developers/api");
    await expect(page.getByRole("heading", { name: "Amplychat public API", level: 1 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Authentication" })).toContainText("Authorization: Bearer");
    const list = page.locator('[data-operation="list_contacts"]');
    await expect(list).toContainText("/public/v1/contacts");
    await expect(list).toContainText("contacts:read");
    await expect(page.locator('[data-operation="send_message"]')).toContainText("messages:send");
    // The app's own routes are not in it.
    await expect(page.getByText("/v1/w/{wid}")).toHaveCount(0);
  });
});
