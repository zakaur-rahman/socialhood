import { expect, test, unique } from "./support/fixtures";

/**
 * F-11 Create a keyword automation: from the template gallery to a draft in the editor, autosave,
 * activation with every missing field reported, then the runtime (run_automation) answering a
 * sandbox DM with the automation's message. GR-13: the template's message is the first step of a
 * flow; a second step is added in the flow editor, and the runtime sends both in order.
 */
test.describe("F-11 create a keyword automation", () => {
  test("a template becomes an active automation that answers a keyword DM", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await page.goto(`/w/${workspace.slug}/automations`);
    await page.getByRole("button", { name: "New automation" }).click();

    // The gallery; one Instagram account, so choosing a template creates the draft at once and
    // the editor opens on it.
    const gallery = page.getByRole("dialog", { name: "New automation" });
    await gallery.getByRole("button", { name: "Use template: Catalogue by DM" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/automations/[0-9a-f-]{36}$`));
    await expect(page.getByRole("textbox", { name: "Automation name" })).toHaveValue("Catalogue by DM");
    await expect(page.getByTestId("status-pill")).toHaveText("Draft");
    await expect(page.getByTestId("save-status")).toHaveText("Saved");

    const when = page.getByRole("region", { name: /^When/ });
    await expect(when.getByRole("radio", { name: "Instagram DM keyword" })).toBeChecked();
    const keywords = page.getByRole("region", { name: /^Keywords/ }).getByRole("list", { name: "Keywords" });
    await expect(keywords).toContainText("catalogue");
    await expect(keywords).toContainText("catalog");

    // The preview renders the personal field, with the fallback when the name is unknown.
    const preview = page.getByRole("tabpanel", { name: "Preview" });
    await expect(preview).toContainText("Hi Priya! Here's our latest catalogue.");
    await preview.getByRole("radio", { name: "Name unknown" }).click();
    await expect(preview).toContainText("Hi there! Here's our latest catalogue.");

    // Activate with the link button still empty: the API returns what's missing and the editor
    // marks it on its step.
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByText("One thing to finish before this can go live.")).toBeVisible();
    const then = page.getByRole("region", { name: /^Then/ });
    const link = then.getByRole("textbox", { name: "Button 1 link" });
    await expect(link).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByTestId("status-pill")).toHaveText("Draft");

    // Fix it: autosave (1 s debounce) says Saving… then Saved, and activation succeeds.
    await link.fill("https://example.com/catalogue");
    await expect(page.getByTestId("save-status")).toHaveText("Saved");
    await expect(link).not.toHaveAttribute("aria-invalid", "true");

    // GR-13: the message is the first step of a flow. Adding a step turns the automation into a
    // flow; the flow editor takes over and keeps the message, its link and its button.
    await then.getByTestId("more-steps").getByRole("button", { name: "Add step" }).click();
    await page.getByRole("menuitem", { name: /^Send/ }).click();
    const flow = then.getByTestId("flow-editor");
    await expect(flow.locator("[data-flow-step]")).toHaveCount(2);
    await expect(flow.getByRole("textbox", { name: "Button 1 link" })).toHaveValue("https://example.com/catalogue");
    await flow
      .locator('[data-kind="send"]')
      .nth(1)
      .getByRole("textbox", { name: "Message" })
      .fill("Anything else? Just reply here.");
    await expect(page.getByTestId("save-status")).toHaveText("Saved");
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByText("Active. It answers new messages from now on.")).toBeVisible();
    await expect(page.getByTestId("status-pill")).toHaveText("Active");
    await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();

    // The list shows it active, with its keywords and no runs yet.
    await page.getByRole("main").getByRole("link", { name: "Automations", exact: true }).click();
    const row = page.getByRole("listitem").filter({ has: page.getByRole("switch", { name: "Active: Catalogue by DM" }) });
    await expect(row.getByRole("switch", { name: "Active: Catalogue by DM" })).toBeChecked();
    await expect(row).toContainText("catalogue");
    await expect(row).toContainText(/0 runs\s*in 7 days/);

    // Runtime: a DM with the keyword gets the automation's message, sent by the sandbox, and the
    // flow's second message follows once the first is delivered.
    const question = unique("Hi! Can I see your catalogue please?");
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: question, fromId: "e2e_f11_cata" });
    await page.goto(`/w/${workspace.slug}/inbox`);
    const conversation = page
      .getByRole("list", { name: "Conversations" })
      .getByRole("link")
      .filter({ hasText: "Anything else? Just reply here." });
    await expect
      .poll(
        async () => {
          await page.reload();
          return conversation.first().waitFor({ timeout: 5_000 }).then(
            () => true,
            () => false,
          );
        },
        { timeout: 60_000, intervals: [500] },
      )
      .toBe(true);
    await conversation.first().click();
    const log = page.getByRole("log", { name: /^Messages with / });
    await expect(log.getByText(question)).toBeVisible();
    // D-07: the bubble's label is "Automation · {name}", never "AI".
    const reply = log.locator("[data-direction='outbound']").filter({ hasText: "Here's our latest catalogue." });
    await expect(reply).toBeVisible();
    await expect(reply.getByText(/^Automation( · .+)?$/)).toBeVisible();
    await expect(reply.getByText(/\bAI\b/)).toHaveCount(0);
    await expect(reply.getByRole("img", { name: "Sent" })).toBeVisible();
    await expect(log.getByText("Anything else? Just reply here.")).toBeVisible();

    await page.goto(`/w/${workspace.slug}/automations`);
    await expect(
      page.getByRole("listitem").filter({ has: page.getByRole("switch", { name: "Active: Catalogue by DM" }) }),
    ).toContainText(/1 run\s*in 7 days/);
  });
});
