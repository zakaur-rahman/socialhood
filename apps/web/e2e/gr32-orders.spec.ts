import type { Api } from "./support/api";
import { expect, test } from "./support/fixtures";

/**
 * GR-32 Orders and payment requests, on the e2e stack: Razorpay is the sandbox (RAZORPAY_PROVIDER=
 * fake, which accepts rzp_test_ keys), and the suite posts the signed webhook Razorpay would send.
 *
 * Done when a test-mode Razorpay link marks the sandbox order paid: connect test keys, make an
 * order in a conversation, send the link, post `payment_link.paid`, and the order is Paid. Also a
 * UPI order marked paid by hand, and Free being told orders are part of Pro.
 */
const WEBHOOK_KEY = "e2e-webhook-secret";

/** A customer's DM and the cotton kurta in the catalogue. */
async function customerAndKurta(
  api: Api,
  wid: string,
  accountId: string,
  fromId: string,
): Promise<{ productId: string; variantId: string }> {
  await api.inbound(wid, { accountId, kind: "dm", text: "I want the kurta", fromId });
  const product = await api.call<{ id: string; variants: { id: string; title: string }[] }>(
    "POST",
    `/v1/w/${wid}/products`,
    { name: "Cotton kurta", variants: [{ title: "Blue / M", price: "799", stock: 12 }] },
  );
  return { productId: product.id, variantId: product.variants[0]?.id ?? "" };
}

test.describe("GR-32 orders and payment requests", () => {
  test("Free sees the Orders page and is told orders are part of Pro", async ({ page, sandbox }) => {
    await page.goto(`/w/${sandbox.workspace.slug}/orders`);
    await expect(page.getByText(/Orders and payment requests are part of Pro/).first()).toBeVisible();
    await expect(page.getByText("No orders yet")).toBeVisible();
  });

  test("a test-mode Razorpay link marks the order paid", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    await customerAndKurta(api, workspace.id, account.id, "e2e_gr32_rzp");

    // Payments: the business's own test keys, checked with the sandbox before they are saved.
    await page.goto(`/w/${workspace.slug}/orders`);
    const payments = page.getByRole("region", { name: "Payments" });
    await payments.getByRole("textbox", { name: "Key id" }).fill("rzp_test_e2eKey1234");
    await payments.getByLabel("Key secret").fill("e2e-key-secret-1");
    await payments.getByLabel("Webhook secret").fill(WEBHOOK_KEY);
    await payments.getByRole("button", { name: "Connect Razorpay" }).click();
    const address = payments.getByTestId("webhook-url");
    await expect(address).toBeVisible();
    const token = ((await address.textContent()) ?? "").trim().split("/").pop() ?? "";
    expect(token.length).toBeGreaterThan(10);

    // An order in the conversation, from the catalogue, then the link in the chat.
    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: "I want the kurta" }).click();
    await page.getByRole("button", { name: "More actions" }).click();
    await page.getByRole("menuitem", { name: "Create order" }).click();
    const dialog = page.getByRole("dialog", { name: "Create order" });
    await dialog.getByLabel("Product 1").selectOption({ label: "Cotton kurta" });
    await dialog.getByLabel("Variant 1").selectOption({ index: 1 });
    await dialog.getByLabel("Quantity 1").fill("2");
    await expect(dialog.getByText(/About .*1,598\.00 in total/)).toBeVisible();
    await dialog.getByRole("button", { name: "Create order" }).click();
    await expect(page.getByRole("dialog", { name: /Order #1 created/ })).toBeVisible();
    await page.getByRole("button", { name: "Send Razorpay link" }).click();
    const log = page.getByRole("log", { name: /^Messages with / });
    const sent = log.locator("[data-direction='outbound']").filter({ hasText: "Order #1" });
    await sent.first().waitFor({ timeout: 30_000 });
    await expect(sent).toContainText("Total: INR 1598.00");
    await expect(sent).toContainText("https://rzp.test/pay/plink_fake_");

    // Razorpay reports the payment: the signed webhook marks the order paid.
    await page.goto(`/w/${workspace.slug}/orders`);
    const row = page.getByTestId("order-row").filter({ hasText: "#1" });
    await expect(row).toContainText("Waiting for payment");
    await row.getByRole("button", { name: /Open/ }).click();
    await expect(page.getByRole("dialog")).toContainText("Cotton kurta");
    const orders = await api.call<{ items: { id: string; total_minor: number; payment_link_url: string }[] }>(
      "GET",
      `/v1/w/${workspace.id}/orders`,
    );
    const placed = orders.items[0];
    const status = await api.razorpayWebhook(token, WEBHOOK_KEY, "e2e-evt-1", {
      event: "payment_link.paid",
      payload: {
        payment_link: {
          entity: {
            id: placed?.payment_link_url.split("/").pop(),
            reference_id: placed?.id,
            amount: placed?.total_minor,
            amount_paid: placed?.total_minor,
            currency: "INR",
            status: "paid",
          },
        },
        payment: { entity: { id: "pay_E2E123", amount: placed?.total_minor } },
      },
    });
    expect(status).toBe(200);
    await expect
      .poll(
        async () => {
          await page.reload();
          await page.getByTestId("order-row").first().waitFor({ timeout: 30_000 });
          return (await page.getByTestId("order-row").filter({ hasText: "#1" }).textContent()) ?? "";
        },
        { timeout: 60_000 },
      )
      .toContain("Paid");
  });

  test("a UPI order is marked paid by hand", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const made = await customerAndKurta(api, workspace.id, account.id, "e2e_gr32_upi");
    await api.call("PUT", `/v1/w/${workspace.id}/integrations/payments/upi`, { vpa: "shop@okbank", name: "Maple" });
    const conversations = await api.call<{ items: { id: string }[] }>("GET", `/v1/w/${workspace.id}/conversations`);
    const created = await api.call<{ id: string; number: number }>("POST", `/v1/w/${workspace.id}/orders`, {
      conversation_id: conversations.items[0]?.id,
      items: [{ product_id: made.productId, variant_id: made.variantId, quantity: 1 }],
    });

    await page.goto(`/w/${workspace.slug}/orders`);
    const row = page.getByTestId("order-row").filter({ hasText: `#${created.number}` });
    await row.getByRole("button", { name: /Open/ }).click();
    const sheet = page.getByRole("dialog");
    await sheet.getByRole("button", { name: "Send UPI request" }).click();
    await expect(sheet.getByText(/UPI has no confirmation from the bank/)).toBeVisible();
    await sheet.getByRole("button", { name: "Mark as paid" }).click();
    await expect(sheet.getByText(/Paid .*marked by/)).toBeVisible();
  });
});
