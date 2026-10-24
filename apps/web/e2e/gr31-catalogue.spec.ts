import { expect, test } from "./support/fixtures";

/**
 * GR-31 Product catalogue, on the e2e stack: the fake AI answers from the PRODUCTS lines it is given
 * (apps/api/scripts/e2e/worker.py), and Shopify is the built-in store (SHOPIFY_PROVIDER=fake, whose
 * products live in Redis, shared by the API and the worker).
 *
 * Done when "price of the blue kurta in M?" gets the right price and link in Suggest; plus adding by
 * hand and by CSV with a preview, the Free plan's upgrade path, Shopify connect and a webhook, and
 * the flow step "send product".
 */
const KURTA_LINK = "https://maple.example/kurta";
const CSV = [
  "name,description,sku,variant,option1_name,option1_value,price,currency,stock,url,active",
  `Cotton kurta,Soft cotton,KUR-BL-S,Blue / S,Colour,Blue,799,INR,4,${KURTA_LINK},yes`,
  "Cotton kurta,,KUR-BL-M,Blue / M,Colour,Blue,799,INR,12,,",
  "Cotton kurta,,KUR-BL-L,Blue / L,Colour,Blue,849.50,INR,0,,",
  "Silk scarf,Hand dyed,SCARF-1,,,,499,INR,,https://maple.example/scarf,yes",
  "Hat,,,,,,lots,INR,,,",
].join("\n");

test.describe("GR-31 product catalogue", () => {
  test("Free sees what exists and is told the catalogue is part of Pro", async ({ page, sandbox }) => {
    await page.goto(`/w/${sandbox.workspace.slug}/products`);
    await expect(page.getByText(/adding, importing and syncing products/)).toBeVisible();
    await page.getByRole("button", { name: "Add product" }).first().click();
    await expect(page.getByRole("heading", { name: /The product catalogue is part of Pro/ })).toBeVisible();
    await expect(page.getByRole("form", { name: "Add a product" })).toHaveCount(0);
  });

  test("adds a product with variants by hand", async ({ page, api, sandbox }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    await page.goto(`/w/${workspace.slug}/products`);
    await page.getByRole("button", { name: "Add product" }).first().click();
    const form = page.getByRole("form", { name: "Add a product" });
    await form.getByRole("textbox", { name: "Name" }).fill("Linen shirt");
    await form.getByRole("button", { name: "Add variant" }).click();
    await form.getByRole("textbox", { name: "Variant name" }).fill("M");
    await form.getByRole("textbox", { name: "Price" }).fill("1299");
    await form.getByRole("textbox", { name: "In stock (optional)" }).fill("3");
    await form.getByRole("button", { name: "Add product" }).click();

    const row = page.getByTestId("product-row").filter({ hasText: "Linen shirt" });
    await expect(row).toBeVisible();
    await expect(row).toContainText("1 variant");
    await expect(row).toContainText("3 in stock");
  });

  test("a CSV file is previewed line by line, then imported; the AI answers the price of the blue kurta in M", async ({
    page,
    api,
    sandbox,
  }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    await api.setAiMode(workspace.id, account.id, "suggest");
    await page.goto(`/w/${workspace.slug}/products`);

    await page.getByRole("button", { name: "Import CSV" }).click();
    const dialog = page.getByRole("dialog", { name: "Import products from a CSV file" });
    await dialog.getByTestId("csv-file-input").setInputFiles({
      name: "products.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(CSV),
    });
    await expect(dialog.getByText("5 lines: 4 new, 0 to update, 1 left out.")).toBeVisible();
    await expect(dialog.getByText("Enter the price as a number, like 799 or 799.50.")).toBeVisible();
    await dialog.getByRole("button", { name: "Import 4 lines" }).click();

    await expect(page.getByTestId("product-row")).toHaveCount(2);
    await expect(page.getByTestId("product-row").filter({ hasText: "Cotton kurta" })).toContainText("3 variants");

    // The done-when: Suggest answers from the catalogue with the variant's price and the link.
    const question = "price of the blue kurta in M?";
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: question, fromId: "e2e_gr31_price" });
    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: question }).click();
    const card = page.getByRole("region", { name: "Conversation", exact: true }).getByRole("region", {
      name: "Suggested reply",
    });
    await expect(card).toContainText("Cotton kurta in Blue / M is INR 799.00.", { timeout: 30_000 });
    await expect(card).toContainText(KURTA_LINK);
  });

  test("connects the built-in Shopify store, copies its products and follows a webhook", async ({
    page,
    api,
    sandbox,
  }) => {
    const { workspace } = sandbox;
    await api.setPlan(workspace.id, "pro");
    await page.goto(`/w/${workspace.slug}/products`);
    const card = page.getByRole("region", { name: "Shopify" });
    await card.getByRole("textbox", { name: /Your store.s address/ }).fill("e2e-store");
    await card.getByRole("button", { name: "Connect Shopify" }).click();
    // The built-in store returns straight to the API's callback, which sends the browser back with a nonce.
    await expect(card.getByText(/Connected to E2e Store/)).toBeVisible({ timeout: 30_000 });
    await expect(page).not.toHaveURL(/shopify=/);

    const rows = page.getByTestId("product-row");
    await rows.first().waitFor({ timeout: 60_000 });
    await expect(rows.filter({ hasText: "Cotton kurta" })).toContainText("4 variants");
    await expect(rows.filter({ hasText: "Silk scarf" })).toContainText("Not tracked");
    await expect(rows.filter({ hasText: "Shopify" })).toHaveCount(3);

    // Shopify says the scarf's price changed: the catalogue follows without a sync.
    const status = await api.shopifyWebhook("products/update", "e2e-store.myshopify.com", {
      id: 9002,
      title: "Silk scarf",
      handle: "silk-scarf",
      status: "active",
      options: [{ name: "Title" }],
      variants: [{ id: 9201, title: "Default Title", sku: "SCARF-1", price: "549.00", option1: "Default Title" }],
    });
    expect(status).toBe(200);
    await expect
      .poll(
        async () => {
          await page.reload();
          await rows.first().waitFor({ timeout: 30_000 });
          return (await rows.filter({ hasText: "Silk scarf" }).textContent()) ?? "";
        },
        { timeout: 60_000 },
      )
      .toContain("549.00");
  });

  test("a flow's product step sends the variant's price and link", async ({ page, api, sandbox }) => {
    const { workspace, account } = sandbox;
    await api.setPlan(workspace.id, "pro");
    const kurta = await api.call<{ id: string; variants: { id: string; title: string }[] }>(
      "POST",
      `/v1/w/${workspace.id}/products`,
      {
        name: "Cotton kurta",
        url: KURTA_LINK,
        variants: [
          { title: "Blue / M", price: "799", stock: 12 },
          { title: "Blue / L", price: "849.50", stock: 0 },
        ],
      },
    );
    const medium = kurta.variants.find((v) => v.title === "Blue / M");
    const keyword = `kurta${Date.now().toString(36)}`;
    await api.flowAutomation(workspace.id, account.id, keyword, {
      start: "p",
      steps: [
        { type: "product", id: "p", product_id: kurta.id, variant_id: medium?.id, intro: "Here it is:" },
      ],
    });
    await api.inbound(workspace.id, { accountId: account.id, kind: "dm", text: keyword, fromId: "e2e_gr31_flow" });

    await page.goto(`/w/${workspace.slug}/inbox`);
    await page.getByRole("list", { name: "Conversations" }).getByRole("link").filter({ hasText: keyword }).click();
    const log = page.getByRole("log", { name: /^Messages with / });
    const sent = log.locator("[data-direction='outbound']").filter({ hasText: "Cotton kurta - Blue / M" });
    await sent.first().waitFor({ timeout: 30_000 });
    await expect(sent).toContainText("INR 799.00");
    await expect(sent).toContainText("In stock");
    await expect(sent).toContainText(KURTA_LINK);
  });
});
