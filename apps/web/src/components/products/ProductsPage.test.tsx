import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Product, ProductList } from "@/lib/api/types";
import { json, noContent, problem, renderWithApi, type Call } from "@/test/api";

import { ProductsPage } from "./ProductsPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
}));

const NOW = "2026-10-25T10:00:00Z";

function product(values: Partial<Product> = {}): Product {
  return {
    id: "p1",
    name: "Silk scarf",
    description: null,
    sku: "SCARF-1",
    currency: "INR",
    price_minor: 49900,
    price: "499.00",
    stock: null,
    url: "https://maple.example/scarf",
    image_asset_id: null,
    image_url: null,
    active: true,
    source: "manual",
    variants: [],
    created_at: NOW,
    updated_at: NOW,
    ...values,
  };
}

const KURTA = product({
  id: "p2",
  name: "Cotton kurta",
  sku: null,
  price_minor: null,
  price: null,
  source: "shopify",
  variants: [
    { id: "v1", title: "Blue / M", options: {}, sku: null, price_minor: 79900, price: "799.00", stock: 12, position: 0 },
    { id: "v2", title: "Blue / L", options: {}, sku: null, price_minor: 84900, price: "849.00", stock: 0, position: 1 },
  ],
});

function list(items: Product[], entitled = true): ProductList {
  return {
    items,
    total: items.length,
    limits: { entitled, product_cap: 1000, import_row_cap: 500, csv_max_chars: 900_000, default_currency: "INR" },
  };
}

const SHOPIFY_OFF = {
  available: false,
  entitled: true,
  connected: false,
  syncing: false,
  products_synced: 0,
  products_skipped: 0,
};

function setup(initial: ProductList, extra: Record<string, (call: Call) => Response> = {}) {
  let current = initial;
  return renderWithApi(<ProductsPage />, {
    upgradeDialog: true,
    handlers: {
      "GET /v1/w/:wid/products": () => json(current),
      "GET /v1/w/:wid/integrations/shopify": () => json(SHOPIFY_OFF),
      "GET /v1/w/:wid/integrations/whatsapp-catalogue": () => json({ entitled: true, connected: false, items_synced: 0, items_pending: 0, items_error: 0, syncing: false, problems: [] }), // GR-33
      "GET /v1/w/:wid/social-accounts": () => json({ items: [] }),
      "POST /v1/w/:wid/products": (call) => {
        const body = call.body as { name: string };
        current = list([product({ id: "new", name: body.name }), ...current.items]);
        return json(current.items[0], 201);
      },
      "DELETE /v1/w/:wid/products/:product_id": (call) => {
        current = list(current.items.filter((item) => !call.path.endsWith(item.id)));
        return noContent();
      },
      ...extra,
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Products page (GR-31)", () => {
  it("lists products with their price, stock and source", async () => {
    setup(list([product(), KURTA]));
    const rows = await screen.findAllByTestId("product-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Silk scarf")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Not tracked")).toBeInTheDocument(); // never recorded, not 0
    expect(within(rows[0]).getByText("Added here")).toBeInTheDocument();
    expect(within(rows[1]).getByText("2 variants")).toBeInTheDocument();
    expect(within(rows[1]).getByText(/₹799\.00 to ₹849\.00/)).toBeInTheDocument();
    expect(within(rows[1]).getByText("12 in stock")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Shopify")).toBeInTheDocument();
  });

  it("searches on the server", async () => {
    const user = userEvent.setup();
    const { calls } = setup(list([product()]));
    await screen.findByText("Silk scarf");
    await user.type(screen.getByRole("searchbox", { name: "Search products" }), "scarf");
    await waitFor(() =>
      expect(
        calls.some((c) => c.method === "GET" && c.path.endsWith("/products") && c.url.searchParams.get("q") === "scarf"),
      ).toBe(true),
    );
  });

  it("explains an empty catalogue and says when a search finds nothing", async () => {
    const user = userEvent.setup();
    setup(list([]));
    expect(await screen.findByText("No products yet")).toBeInTheDocument();
    expect(screen.getByText(/connect Shopify/)).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: "Search products" }), "zzz");
    expect(await screen.findByText("No products match")).toBeInTheDocument();
  });

  it("on Free shows what exists, says the catalogue is part of Pro, and opens the upgrade dialog instead of the form", async () => {
    const user = userEvent.setup();
    setup(list([product()], false));
    expect(await screen.findByText("Silk scarf")).toBeInTheDocument();
    expect(screen.getByText(/adding, importing and syncing products/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Add product/ })[0]);
    expect(await screen.findByRole("heading", { name: /The product catalogue is part of Pro/ })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Add a product" })).not.toBeInTheDocument();
  });

  it("adds a product with a price and sends the API's body", async () => {
    const user = userEvent.setup();
    const { calls } = setup(list([]));
    await screen.findByText("No products yet");
    await user.click(screen.getAllByRole("button", { name: /Add product/ })[0]);
    const form = await screen.findByRole("form", { name: "Add a product" });
    await user.click(within(form).getByRole("button", { name: "Add product" }));
    expect(await within(form).findByText("Enter the product's name.")).toBeInTheDocument();
    expect(within(form).getByText("Enter a price.")).toBeInTheDocument();

    await user.type(within(form).getByRole("textbox", { name: "Name" }), "Linen shirt");
    await user.type(within(form).getByRole("textbox", { name: "Price" }), "1299");
    await user.click(within(form).getByRole("button", { name: "Add product" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Product added"));
    const body = calls.find((c) => c.method === "POST" && c.path.endsWith("/products"))?.body as Record<string, unknown>;
    expect(body).toMatchObject({ name: "Linen shirt", price: "1299", currency: "INR", stock: null, variants: [], active: true });
    expect(await screen.findByText("Linen shirt")).toBeInTheDocument();
  });

  it("gives each variant its own price and stock, and drops the product's own", async () => {
    const user = userEvent.setup();
    const { calls } = setup(list([]));
    await screen.findByText("No products yet");
    await user.click(screen.getAllByRole("button", { name: /Add product/ })[0]);
    const form = await screen.findByRole("form", { name: "Add a product" });
    await user.type(within(form).getByRole("textbox", { name: "Name" }), "Cotton kurta");
    await user.click(within(form).getByRole("button", { name: "Add variant" }));
    await user.type(within(form).getByRole("textbox", { name: "Variant name" }), "Blue / M");
    await user.type(within(form).getByRole("textbox", { name: "Price" }), "799");
    await user.type(within(form).getByRole("textbox", { name: "In stock (optional)" }), "12");
    await user.click(within(form).getByRole("button", { name: "Add product" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Product added"));
    const body = calls.find((c) => c.method === "POST" && c.path.endsWith("/products"))?.body as {
      price: unknown;
      variants: unknown[];
    };
    expect(body.price).toBeNull();
    expect(body.variants).toEqual([{ title: "Blue / M", options: {}, sku: null, price: "799", stock: 12 }]);
  });

  it("shows the API's plan answer inline and keeps what was typed", async () => {
    const user = userEvent.setup();
    setup(list([]), {
      "POST /v1/w/:wid/products": () =>
        problem(402, "quota_exceeded", "Your plan includes 1,000 products.", {
          entitlement: "catalogue_products",
          limit: 1000,
        }),
    });
    await screen.findByText("No products yet");
    await user.click(screen.getAllByRole("button", { name: /Add product/ })[0]);
    const form = await screen.findByRole("form", { name: "Add a product" });
    await user.type(within(form).getByRole("textbox", { name: "Name" }), "Linen shirt");
    await user.type(within(form).getByRole("textbox", { name: "Price" }), "10");
    await user.click(within(form).getByRole("button", { name: "Add product" }));
    expect(await within(form).findByText(/Your plan includes 1,000 products/)).toBeInTheDocument();
    expect(within(form).getByRole("textbox", { name: "Name" })).toHaveValue("Linen shirt");
  });

  it("deletes after asking", async () => {
    const user = userEvent.setup();
    setup(list([product(), KURTA]));
    await screen.findByText("Silk scarf");
    await user.click(screen.getByRole("button", { name: "Delete Silk scarf" }));
    expect(await screen.findByText(/A flow that sends this product will stop at that step/)).toBeInTheDocument();
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Product deleted"));
    await waitFor(() => expect(screen.queryByText("Silk scarf")).not.toBeInTheDocument());
  });
});
