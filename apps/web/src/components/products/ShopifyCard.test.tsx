import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ShopifyStatus } from "@/lib/api/types";
import { browser } from "@/lib/billing/browser";
import { json, noContent, problem, renderWithApi, type Call } from "@/test/api";

import { ShopifyCard } from "./ShopifyCard";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const nav = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
}));

function status(values: Partial<ShopifyStatus> = {}): ShopifyStatus {
  return {
    available: true,
    entitled: true,
    connected: false,
    syncing: false,
    products_synced: 0,
    products_skipped: 0,
    ...values,
  } as ShopifyStatus;
}

const CONNECTED = {
  connected: true,
  status: "active" as const,
  shop_domain: "my-store.myshopify.com",
  shop_name: "My Store",
  synced_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  products_synced: 3,
};

function setup(initial: ShopifyStatus, extra: Record<string, (call: Call) => Response> = {}) {
  let current = initial;
  return renderWithApi(<ShopifyCard wid="w1" />, {
    handlers: {
      "GET /v1/w/:wid/integrations/shopify": () => json(current),
      "POST /v1/w/:wid/integrations/shopify/connect": () =>
        json({ authorize_url: "https://my-store.myshopify.com/admin/oauth/authorize?state=s1" }),
      "POST /v1/w/:wid/integrations/shopify/complete": () => {
        current = status({ ...CONNECTED, syncing: true });
        return json(current);
      },
      "POST /v1/w/:wid/integrations/shopify/sync": () => {
        current = { ...current, syncing: true };
        return json(current, 202);
      },
      "DELETE /v1/w/:wid/integrations/shopify": () => {
        current = status();
        return noContent();
      },
      ...extra,
    },
  });
}

beforeEach(() => {
  nav.search = "";
  toast.success.mockReset();
  toast.error.mockReset();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("Shopify card (GR-31)", () => {
  it("says when the Shopify app isn't set up on the server", async () => {
    setup(status({ available: false }));
    expect(await screen.findByText(/Shopify isn.t set up on this server yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect Shopify" })).not.toBeInTheDocument();
  });

  it("says Shopify import is part of Pro on a plan without the catalogue", async () => {
    setup(status({ entitled: false }));
    expect(await screen.findByText(/with Shopify import, is part of Pro/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect Shopify" })).not.toBeInTheDocument();
  });

  it("sends the member to Shopify with the store they typed", async () => {
    const assign = vi.spyOn(browser, "assign").mockImplementation(() => {});
    const user = userEvent.setup();
    const { calls } = setup(status());
    expect(await screen.findByText("Not connected")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: /Your store.s address/ }), "my-store");
    await user.click(screen.getByRole("button", { name: "Connect Shopify" }));
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith("https://my-store.myshopify.com/admin/oauth/authorize?state=s1"),
    );
    expect(calls.find((c) => c.path.endsWith("/shopify/connect"))?.body).toEqual({ shop: "my-store" });
  });

  it("shows why a store address was refused on the field", async () => {
    const user = userEvent.setup();
    setup(status(), {
      "POST /v1/w/:wid/integrations/shopify/connect": () =>
        new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Validation error",
            status: 422,
            code: "validation_error",
            errors: [{ field: "shop", message: "Enter your store's address, like my-store.myshopify.com." }],
          }),
          { status: 422, headers: { "Content-Type": "application/problem+json" } },
        ),
    });
    const field = await screen.findByRole("textbox", { name: /Your store.s address/ });
    await user.type(field, "evil.example.com");
    await user.click(screen.getByRole("button", { name: "Connect Shopify" }));
    expect(await screen.findByText(/Enter your store's address, like/)).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
  });

  it("finishes a connect with the nonce once, and drops it from the address", async () => {
    nav.search = "shopify=n0nce";
    const replace = vi.spyOn(window.history, "replaceState");
    const { calls } = setup(status());
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Shopify connected. Your products are being copied."),
    );
    expect(calls.filter((c) => c.path.endsWith("/shopify/complete")).map((c) => c.body)).toEqual([{ nonce: "n0nce" }]);
    expect(replace).toHaveBeenCalled();
    expect(await screen.findByText(/Connected to My Store \(my-store.myshopify.com\)/)).toBeInTheDocument();
    expect(screen.getByText(/Copying products now/)).toBeInTheDocument();
  });

  it.each([
    [404, "That connection link expired. Connect Shopify again."],
    [
      403,
      "This Shopify connection was started by someone else, so it wasn't added. To connect your own store, use Connect Shopify.",
    ],
  ])("explains a refused nonce (%s)", async (code, message) => {
    nav.search = "shopify=n0nce";
    setup(status(), {
      "POST /v1/w/:wid/integrations/shopify/complete": () =>
        problem(code, code === 404 ? "not_found" : "forbidden", "x"),
    });
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
  });

  it("explains a cancelled install without calling the API", async () => {
    nav.search = "error=access_denied";
    const { calls } = setup(status());
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Shopify wasn't connected: you cancelled it."));
    expect(calls.some((c) => c.path.endsWith("/complete"))).toBe(false);
  });

  it("shows the last sync and syncs again on request", async () => {
    const user = userEvent.setup();
    const { calls } = setup(status(CONNECTED));
    expect(await screen.findByText(/3 products copied 5m ago/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sync now" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Copying your products again."));
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/shopify/sync"))).toBe(true);
  });

  it("asks for a reconnect when access was removed", async () => {
    setup(
      status({
        ...CONNECTED,
        status: "needs_reconnect",
        sync_error: "Access was removed in Shopify. Reconnect to keep your products in step.",
      }),
    );
    expect(await screen.findByText("Reconnect needed")).toBeInTheDocument();
    expect(screen.getByText(/Access was removed in Shopify/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconnect Shopify" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sync now" })).not.toBeInTheDocument();
  });

  it("disconnects after asking, removing the products unless they are kept", async () => {
    const user = userEvent.setup();
    const { calls } = setup(status(CONNECTED));
    await user.click(await screen.findByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("checkbox", { name: "Keep the products I already have" }));
    await user.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Shopify disconnected."));
    expect(calls.find((c) => c.method === "DELETE")?.url.searchParams.get("keep_products")).toBe("true");
  });
});
