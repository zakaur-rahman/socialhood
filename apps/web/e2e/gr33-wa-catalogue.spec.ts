import type { Api } from "./support/api";
import { expect, test } from "./support/fixtures";

/**
 * GR-33 WhatsApp catalogue messages (C-215: a scheduled feed), on the e2e stack with a sandbox
 * WhatsApp number. Connect a catalogue, fetch its feed link as Meta would so the products count as
 * in the catalogue, send a product message from the inbox, and turn a customer's cart into an
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
  test("a catalogue is connected, Meta fetches its feed and a product message is sent", async ({ page, api, sandbox, request }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const wa = await api.connectSandbox(workspace.id, "whatsapp");
    await kurta(api, workspace.id);

    await page.goto(`/w/${workspace.slug}/products`);
    const card = page.getByRole("region", { name: "WhatsApp catalogue" });
    await card.getByLabel("Catalogue id").fill("100000000033");
    await card.getByRole("button", { name: "Connect catalogue" }).click();
    await expect(card.getByText(/Connected to catalogue 100000000033/)).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText(/Meta hasn't fetched your products yet/)).toBeVisible();
    await expect(card.getByRole("button", { name: /Sync/ })).toHaveCount(0);

    // Meta fetches the feed link; that fetch is what puts the items in the catalogue.
    const feed = await request.get(await card.getByLabel("Feed link").inputValue());
    expect(feed.ok()).toBe(true);
    expect(await feed.text()).toContain("Cotton kurta");
    await page.reload();
    await expect(card.getByText(/Meta last fetched your products/)).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText("In the catalogue").locator("xpath=following-sibling::dd")).toHaveText("2");

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
