import type { Api } from "./support/api";
import { expect, test } from "./support/fixtures";

/**
 * GR-32 follow-ups, on the e2e stack (Razorpay is the sandbox, RAZORPAY_PROVIDER=fake). A UPI order
 * is paid in two parts by hand (the order is "Partly paid" after the first), marked shipped with a
 * note, and refunded with a reason (a UPI payment is paid back by the business, so the refund is
 * recorded). Another order is edited while it is a draft and gets its new total.
 */
async function customerAndKurta(
  api: Api,
  wid: string,
  accountId: string,
  fromId: string,
): Promise<{ conversationId: string; productId: string; variantId: string }> {
  await api.inbound(wid, { accountId, kind: "dm", text: "I want the kurta", fromId });
  const product = await api.call<{ id: string; variants: { id: string }[] }>("POST", `/v1/w/${wid}/products`, {
    name: "Cotton kurta",
    variants: [{ title: "Blue / M", price: "799", stock: 12 }],
  });
  // The worker stores the message a moment after the event is injected.
  const firstConversation = async () =>
    (await api.call<{ items: { id: string }[] }>("GET", `/v1/w/${wid}/conversations`)).items[0]?.id ?? "";
  await expect.poll(firstConversation, { timeout: 30_000 }).not.toBe("");
  return {
    conversationId: await firstConversation(),
    productId: product.id,
    variantId: product.variants[0]?.id ?? "",
  };
}

test.describe("GR-32 follow-ups", () => {
  test("a UPI order is paid in parts, shipped and refunded", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const made = await customerAndKurta(api, workspace.id, account.id, "e2e_followups_orders");
    await api.call("PUT", `/v1/w/${workspace.id}/integrations/payments/upi`, { vpa: "shop@okbank", name: "Maple" });
    const created = await api.call<{ id: string; number: number }>("POST", `/v1/w/${workspace.id}/orders`, {
      conversation_id: made.conversationId,
      items: [{ product_id: made.productId, variant_id: made.variantId, quantity: 2 }],
    });

    await page.goto(`/w/${workspace.slug}/orders`);
    await page
      .getByTestId("order-row")
      .filter({ hasText: `#${created.number}` })
      .getByRole("button", { name: /Open/ })
      .click();
    const sheet = page.getByRole("dialog");

    // The first part: INR 500.00 of 1,598.00.
    await sheet.getByLabel(/Amount received/).fill("500");
    await sheet.getByLabel(/Payment reference/).fill("UTR 1");
    await sheet.getByRole("button", { name: "Record payment" }).click();
    await expect(sheet.getByText("Partly paid").first()).toBeVisible();
    await expect(sheet.getByText("Left to pay")).toBeVisible();
    await expect(sheet.getByRole("button", { name: "Cancel order" })).toHaveCount(0);

    // The rest in one go.
    await sheet.getByRole("button", { name: "Mark as paid" }).click();
    await expect(sheet.getByText("Paid", { exact: true }).first()).toBeVisible();

    // Shipped, with a note.
    await sheet.getByLabel(/Shipping note/).fill("Delhivery 123456");
    await sheet.getByRole("button", { name: "Mark as shipped" }).click();
    await expect(sheet.getByText("Shipped", { exact: true }).first()).toBeVisible();
    await expect(sheet.getByText(/Delhivery 123456/)).toBeVisible();

    // Refunded, with a reason.
    await sheet.getByLabel("Reason").fill("Returned by the customer");
    await sheet.getByRole("button", { name: "Refund" }).click();
    await expect(sheet.getByText("Refunded", { exact: true }).first()).toBeVisible();
    await expect(sheet.getByText(/Returned by the customer/).first()).toBeVisible();
  });

  test("a draft order is changed and gets its new total", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const made = await customerAndKurta(api, workspace.id, account.id, "e2e_followups_edit");
    const created = await api.call<{ id: string; number: number }>("POST", `/v1/w/${workspace.id}/orders`, {
      conversation_id: made.conversationId,
      items: [{ product_id: made.productId, variant_id: made.variantId, quantity: 1 }],
    });

    await page.goto(`/w/${workspace.slug}/orders`);
    await page
      .getByTestId("order-row")
      .filter({ hasText: `#${created.number}` })
      .getByRole("button", { name: /Open/ })
      .click();
    await page.getByRole("dialog").getByRole("button", { name: "Edit order" }).click();
    const edit = page.getByRole("dialog", { name: new RegExp(`Change order #${created.number}`) });
    await edit.getByLabel("Quantity 1").fill("3");
    await edit.getByLabel("Note").fill("Gift wrap please");
    await edit.getByRole("button", { name: "Save changes" }).click();
    await expect(edit).toBeHidden();

    const sheet = page.getByRole("dialog");
    await expect(sheet).toContainText("3 x Cotton kurta");
    await expect(sheet).toContainText(/2,397\.00/);
    await expect(sheet).toContainText("Gift wrap please");
  });
});
