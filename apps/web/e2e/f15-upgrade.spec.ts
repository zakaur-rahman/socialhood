import { randomUUID } from "node:crypto";

import { BASE_URL, E2E_USER } from "./support/env";
import { expect, test } from "./support/fixtures";

/**
 * F-15 Upgrade after hitting a limit. A Free workspace with 3 active automations tries to
 * activate a fourth: the API answers 402 and the upgrade dialog names the limit, with the Pro
 * price and the trial. Checkout goes to the fake Dodo (DODO_PROVIDER=fake: a checkout URL on a
 * .invalid host, which this test serves as a stand-in page that sends the browser back), the
 * billing page waits, and only Dodo's signed subscription.active webhook, posted here with the
 * stack's DODO_WEBHOOK_SECRET, turns Pro on. Then the fourth automation activates.
 */
test.describe("F-15 upgrade after hitting a limit", () => {
  test("the automation limit leads to checkout, and the signed webhook turns Pro on", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    for (const keyword of ["alpha", "bravo", "charlie"]) await api.activeAutomation(workspace.id, account.id, keyword);

    // A fourth automation, ready to go live.
    await page.goto(`/w/${workspace.slug}/automations`);
    await expect(page.getByRole("switch", { name: /^Active: / })).toHaveCount(3);
    await page.getByRole("button", { name: "New automation" }).click();
    await page.getByRole("dialog", { name: "New automation" }).getByRole("button", { name: "Use template: Book a call" }).click();
    await expect(page).toHaveURL(new RegExp(`/w/${workspace.slug}/automations/[0-9a-f-]{36}$`));
    const editorUrl = page.url();
    await page.getByRole("textbox", { name: "Button 1 link" }).fill("https://example.com/book");
    await expect(page.getByTestId("save-status")).toHaveText("Saved");

    // Hit the limit: 402, and the upgrade dialog names it.
    const refused = page.waitForResponse((r) => /\/automations\/[^/]+\/activate$/.test(r.url()));
    await page.getByRole("button", { name: "Activate" }).click();
    expect((await refused).status()).toBe(402);
    const dialog = page.getByRole("dialog", { name: "Automation limit reached" });
    await expect(dialog).toContainText("Free includes 3 active automations");
    await expect(dialog).toContainText("Pro includes 50 active automations");
    await expect(dialog).toContainText("₹999 a month");
    await expect(page.getByTestId("status-pill")).toHaveText("Draft");

    // Checkout: the browser goes to (the fake) Dodo, which sends it back to the billing page.
    const returnUrl = `${BASE_URL}/w/${workspace.slug}/settings/billing?checkout=return`;
    await page.route("https://checkout.dodo.invalid/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/html",
        body: `<!doctype html><title>Dodo checkout (e2e stand-in)</title><h1>Checkout</h1><a href="${returnUrl}">Return to Social Hood</a>`,
      }),
    );
    const checkout = page.waitForResponse((r) => r.url().endsWith("/billing/checkout") && r.request().method() === "POST");
    await dialog.getByRole("button", { name: "Start 7-day trial" }).click();
    expect((await checkout).status()).toBe(200);
    await expect(page).toHaveURL(/^https:\/\/checkout\.dodo\.invalid\/session\//);
    await page.getByRole("link", { name: "Return to Social Hood" }).click();

    // Back from Dodo: the page waits; the return URL alone changes nothing.
    await expect(page).toHaveURL(returnUrl);
    const notice = page.getByRole("status").filter({ hasText: /Confirming your payment…|Your Pro trial has started/ });
    await expect(notice).toContainText("Confirming your payment…");
    await expect(page.getByRole("region", { name: "Free" })).toBeVisible();

    // Dodo's signed webhook: subscription.active for this workspace's checkout, in its trial.
    const now = new Date();
    const status = await api.dodoWebhook({
      business_id: "bus_e2e",
      type: "subscription.active",
      timestamp: now.toISOString(),
      data: {
        payload_type: "Subscription",
        subscription_id: `sub_e2e_${randomUUID()}`,
        product_id: api.proProduct,
        status: "active",
        quantity: 1,
        currency: "INR",
        recurring_pre_tax_amount: 99900,
        trial_period_days: 7,
        created_at: now.toISOString(),
        previous_billing_date: now.toISOString(),
        next_billing_date: new Date(now.getTime() + 7 * 24 * 3600 * 1000).toISOString(),
        cancel_at_next_billing_date: false,
        customer: { customer_id: "cus_e2e", name: `${E2E_USER.firstName} ${E2E_USER.lastName}`, email: E2E_USER.email },
        metadata: { workspace_id: workspace.id },
      },
    });
    expect(status).toBe(200);

    // usage.updated (or the 3 s poll): Pro is on, and the limits follow.
    await expect(notice).toContainText("Your Pro trial has started");
    await expect(page.getByRole("region", { name: "Pro" }).getByRole("heading", { name: "Pro", level: 2 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Usage" })).toContainText("3 of 50 automations");

    // The automation that hit the limit now goes live.
    await page.goto(editorUrl);
    await page.getByRole("button", { name: "Activate" }).click();
    await expect(page.getByText("Active. It answers new messages from now on.")).toBeVisible();
    await expect(page.getByTestId("status-pill")).toHaveText("Active");
  });
});
