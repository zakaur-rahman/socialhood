import type { Api } from "./support/api";
import { expect, test } from "./support/fixtures";

/**
 * GR-33 WhatsApp catalogue messages, on the e2e stack with a sandbox WhatsApp number: its Meta
 * catalogue is the built-in sandbox (sandbox numbers never reach Meta). Connect a catalogue, let
 * the products sync, send a product message from the inbox, and turn a customer's cart into an
 * order awaiting payment.
 */
const PICTURE = "https://cdn.example/kurta.jpg";

type Kurta = { id: string; variants: { id: string; title: string }[] };

async function kurta(api: Api, wid: string): Promise<Kurta> {
  return api.call<Kurta>("POST", `/v1/w/${wid}/products`, {
    name: "Cotton kurta",
    url: "https://maple.example/kurta",
    image_url: PICTURE,
    variants: [
      { title: "Blue / M", price: "799", stock: 12 },
      { title: "Blue / L", price: "849", stock: 3 },
    ],
  });
}

test.describe("GR-33 WhatsApp catalogue messages", () => {
  test("a catalogue is connected, its products sync and a product message is sent", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const wa = await api.connectSandbox(workspace.id, "whatsapp");
    await kurta(api, workspace.id);

    await page.goto(`/w/${workspace.slug}/products`);
    const card = page.getByRole("region", { name: "WhatsApp catalogue" });
    await card.getByLabel("Catalogue id").fill("e2e-catalog-1");
    await card.getByRole("button", { name: "Connect catalogue" }).click();
    await expect(card.getByText(/Connected to .*e2e-catalog-1/)).toBeVisible({ timeout: 30_000 });
    // The first sync runs in the worker; the card polls while it does.
    await expect(card.getByText(/2 items in the catalogue/)).toBeVisible({ timeout: 60_000 });

    await api.inbound(workspace.id, { accountId: wa.id, kind: "dm", text: "Do you have a kurta?", fromId: "919800000033" });
    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: "Do you have a kurta?" }).click();
    await page.getByRole("button", { name: "More actions" }).click();
    await page.getByRole("menuitem", { name: "Send product", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Send product" });
    await dialog.getByLabel("Message").fill("This one in blue?");
    await dialog.getByLabel("Product").selectOption({ label: "Cotton kurta - Blue / M (₹799.00)" });
    await dialog.getByRole("button", { name: "Send" }).click();

    const log = page.getByRole("log", { name: /^Messages with / });
    await expect(log.locator("[data-direction='outbound']").filter({ hasText: "This one in blue?" }).first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("a customer's cart becomes an order awaiting payment", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const wa = await api.connectSandbox(workspace.id, "whatsapp");
    const product = await kurta(api, workspace.id);
    const medium = product.variants.find((v) => v.title === "Blue / M");

    await api.inbound(workspace.id, {
      accountId: wa.id,
      kind: "order",
      fromId: "919800000034",
      text: "Gift wrap please",
      cart: [{ retailerId: medium?.id ?? "", quantity: 2, price: "799.00" }],
    });

    await page.goto(`/w/${workspace.slug}/orders`);
    const row = page.getByTestId("order-row").first();
    await row.waitFor({ timeout: 30_000 });
    await expect(row).toContainText("Waiting for payment");
    await expect(row).toContainText("2 x Cotton kurta - Blue / M");
    await expect(row).toContainText("1,598.00");
  });
});
