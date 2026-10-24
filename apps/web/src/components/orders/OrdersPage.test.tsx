import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Order, OrderList, PaymentSettings } from "@/lib/api/types";
import { json, renderWithApi, type Call } from "@/test/api";

import { OrdersPage } from "./OrdersPage";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const NOW = "2026-10-25T10:00:00Z";

function order(values: Partial<Order> = {}): Order {
  return {
    id: "o1",
    number: 12,
    status: "awaiting_payment",
    source: "inbox",
    currency: "INR",
    total_minor: 159800,
    total: "1598.00",
    items: [
      {
        id: "l1",
        product_id: "p1",
        variant_id: "v1",
        name: "Cotton kurta",
        variant_title: "Blue / M",
        sku: null,
        quantity: 2,
        unit_price_minor: 79900,
        unit_price: "799.00",
        line_total_minor: 159800,
        line_total: "1598.00",
      },
    ],
    address: { name: "Priya Shah", city: "Pune" },
    note: null,
    contact: { id: "c1", display_name: "Priya Shah", username: "priya.shah" },
    conversation_id: "conv1",
    payment_method: "upi",
    payment_link_url: "upi://pay?pa=shop%40okbank",
    payment_reference: null,
    link_expires_at: null,
    paid_at: null,
    paid_by_name: null,
    cancelled_at: null,
    created_by_name: "Sam",
    created_at: NOW,
    updated_at: NOW,
    ...values,
  };
}

function list(items: Order[], entitled = true): OrderList {
  return { items, total: items.length, limits: { entitled, razorpay_ready: true, upi_ready: true } };
}

const SETTINGS: PaymentSettings = {
  entitled: true,
  razorpay_connected: false,
  razorpay_test_mode: false,
  webhook_events: [],
  upi_vpa: null,
  upi_name: null,
};

function setup(initial: OrderList, extra: Record<string, (call: Call) => Response> = {}) {
  let current = initial;
  return renderWithApi(<OrdersPage />, {
    upgradeDialog: true,
    handlers: {
      "GET /v1/w/:wid/orders": () => json(current),
      "GET /v1/w/:wid/integrations/payments": () => json(SETTINGS),
      "POST /v1/w/:wid/orders/:order_id/mark-paid": () => {
        const paid = order({ status: "paid", paid_at: NOW, paid_by_name: "Sam" });
        current = list([paid]);
        return json(paid);
      },
      ...extra,
    },
  });
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("Orders page (GR-32)", () => {
  it("lists orders with their number, customer, items, total and status", async () => {
    setup(list([order(), order({ id: "o2", number: 13, status: "paid" })]));
    const rows = await screen.findAllByTestId("order-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("#12")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Priya Shah")).toBeInTheDocument();
    expect(within(rows[0]).getByText("2 x Cotton kurta - Blue / M")).toBeInTheDocument();
    expect(within(rows[0]).getByText(/₹1,598\.00/)).toBeInTheDocument();
    expect(within(rows[0]).getByText("Waiting for payment")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Paid")).toBeInTheDocument();
  });

  it("tells Free that orders are part of Pro", async () => {
    setup(list([], false));
    expect(await screen.findByText(/Orders and payment requests are part of Pro\. You can see what is here/)).toBeInTheDocument();
    expect(await screen.findByText("No orders yet")).toBeInTheDocument();
  });

  it("says a UPI order has no bank confirmation and marks it paid by hand", async () => {
    const user = userEvent.setup();
    setup(list([order()]));
    await user.click(await screen.findByRole("button", { name: /Open/ }));
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByText(/UPI has no confirmation from the bank/)).toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "Mark as paid" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Order #12 marked paid."));
    expect(await within(await screen.findByRole("dialog")).findByText(/marked by Sam/)).toBeInTheDocument();
  });

  it("offers a payment link only for orders that can still be paid", async () => {
    const user = userEvent.setup();
    setup(list([order({ status: "paid", paid_at: NOW })]));
    await user.click(await screen.findByRole("button", { name: /Open/ }));
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).queryByRole("button", { name: "Send Razorpay link" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "Mark as paid" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "Cancel order" })).not.toBeInTheDocument();
  });
});
