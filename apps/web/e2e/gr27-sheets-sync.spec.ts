import { expect, test } from "./support/fixtures";

/**
 * GR-27 Google Sheets sync on the fake Google (GOOGLE_PROVIDER=fake: "signing in" returns straight to
 * the API's callback, and the sheets and rows live in Redis, shared by the API and the worker).
 * On Pro the member connects Google, creates a sheet, maps the columns and sends a test row; a
 * flow's captured email appears as a row within a minute; a deleted sheet fails the next row with a
 * plain reason. On Free the card says Sheets sync is part of Pro.
 */
test.describe("GR-27 Google Sheets sync", () => {
  test("Free is told Sheets sync is part of Pro", async ({ page, sandbox }) => {
    await page.goto(`/w/${sandbox.workspace.slug}/settings/integrations`);
    const card = page.getByRole("region", { name: "Google Sheets" });
    await expect(card.getByText(/Google Sheets sync is part of Pro/)).toBeVisible();
    await expect(card.getByRole("button", { name: "Connect Google" })).toHaveCount(0);
  });

  test("a captured lead appears as a row, and a deleted sheet says why", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");

    await page.goto(`/w/${workspace.slug}/settings/integrations`);
    const card = page.getByRole("region", { name: "Google Sheets" });
    await card.getByRole("button", { name: "Connect Google" }).click();
    // The fake Google returns to the API's callback, which sends the browser back here with a nonce.
    await expect(card.getByText("Connected as owner@example.com.")).toBeVisible({ timeout: 30_000 });
    await expect(page).not.toHaveURL(/google=/);

    await card.getByRole("textbox", { name: "New sheet name" }).fill("E2E leads");
    await card.getByRole("button", { name: "Create sheet" }).click();
    const sheetLink = card.getByRole("link", { name: /E2E leads/ });
    await expect(sheetLink).toBeVisible();
    const sheetId = (await sheetLink.getAttribute("href"))?.split("/").pop() ?? "";
    expect(sheetId).toMatch(/^fake-sheet-/);

    // Map: email, then the automation; drop the rest.
    const columns = card.getByRole("list", { name: "Columns" });
    for (const label of ["Username", "Platform", "Phone", "Captured at", "Consent", "Name"]) {
      await columns.getByRole("button", { name: `Remove ${label}` }).click();
    }
    await card.getByRole("button", { name: "Save columns" }).click();
    await expect(card.getByRole("button", { name: "Save columns" })).toBeDisabled();
    await expect.poll(async () => (await api.googleSheet(sheetId)).header).toEqual(["Email", "Automation"]);

    await card.getByRole("button", { name: "Send a test row" }).click();
    await expect.poll(async () => (await api.googleSheet(sheetId)).rows, { timeout: 30_000 }).toEqual([
      ["test@example.com", "Test row from Social Hood"],
    ]);

    // A real capture: the flow asks for an email.
    const keyword = `sheet${Date.now().toString(36)}`;
    const automation = await api.flowAutomation(workspace.id, account.id, keyword, {
      start: "q",
      steps: [{ type: "ask", id: "q", text: "What's your email?", expect: "email" }],
    });
    const fromId = `e2e_gr27_${Date.now().toString(36)}`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId });
    await expect
      .poll(
        async () =>
          (await api.call<{ items: { result: string }[] }>("GET", `/v1/w/${workspace.id}/automations/${automation.id}/runs`))
            .items[0]?.result,
        { timeout: 30_000 },
      )
      .toBe("awaiting_reply");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "Priya@Example.com", fromId });

    await expect
      .poll(async () => (await api.googleSheet(sheetId)).rows.map((r) => r[0]), { timeout: 60_000 })
      .toContain("priya@example.com");

    await page.reload();
    await card.getByTestId("sheet-row").first().waitFor({ timeout: 30_000 });
    await expect(card.getByTestId("sheet-row").first()).toContainText("Added");

    // The sheet is deleted in Google: the next lead's row fails with a plain reason, no retry.
    await api.deleteGoogleSheet(sheetId);
    const second = `${keyword}b`;
    const again = await api.flowAutomation(workspace.id, account.id, second, {
      start: "q",
      steps: [{ type: "ask", id: "q", text: "What's your email?", expect: "email" }],
    });
    const fromTwo = `${fromId}b`;
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: second, fromId: fromTwo });
    await expect
      .poll(
        async () =>
          (await api.call<{ items: { result: string }[] }>("GET", `/v1/w/${workspace.id}/automations/${again.id}/runs`))
            .items[0]?.result,
        { timeout: 30_000 },
      )
      .toBe("awaiting_reply");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: "second@example.com", fromId: fromTwo });

    await expect
      .poll(
        async () => {
          await page.reload();
          await card.getByTestId("sheet-row").first().waitFor({ timeout: 30_000 });
          return card.getByTestId("sheet-row").first().innerText();
        },
        { timeout: 60_000 },
      )
      .toContain("Google said the sheet was deleted. Pick or create a sheet again.");
  });

  test("disconnecting removes the connection", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    await page.goto(`/w/${workspace.slug}/settings/integrations`);
    const card = page.getByRole("region", { name: "Google Sheets" });
    await card.getByRole("button", { name: "Connect Google" }).click();
    await expect(card.getByText("Connected as owner@example.com.")).toBeVisible({ timeout: 30_000 });

    await card.getByRole("button", { name: "Disconnect" }).click();
    await page.getByRole("alertdialog", { name: "Disconnect Google?" }).getByRole("button", { name: "Disconnect Google" }).click();
    await expect(card.getByRole("button", { name: "Connect Google" })).toBeVisible();
    await expect(card.getByText("Not connected")).toBeVisible();
  });
});
