import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Order, OrderList } from "@/lib/api/types";
import { json, renderWithApi, type Call } from "@/test/api";

import { OrderSheet } from "./OrderSheet";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const NOW = "2026-10-26T10:00:00Z";
const LIMITS: OrderList["limits"] = { entitled: true, razorpay_ready: true, upi_ready: true };

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
    address: null,
    note: null,
    contact: { id: "c1", display_name: "Priya Shah", username: "priya.shah" },
    conversation_id: "conv1",
    social_account_id: "acc1",
    platform: "instagram",
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
    amount_paid_minor: 0,
    amount_paid: "0.00",
    amount_left_minor: 159800,
    amount_left: "1598.00",
    amount_refunded_minor: 0,
    amount_refunded: "0.00",
    refundable_minor: 0,
    refundable: "0.00",
    accept_partial: false,
    fulfilled_at: null,
    fulfilment_note: null,
    payments: [],
    refunds: [],
    notice: null,
    ...values,
  } as Order;
}

const PAID = order({
  status: "paid",
  paid_at: NOW,
  paid_by_name: "Sam",
  amount_paid_minor: 159800,
  amount_paid: "1598.00",
  amount_left_minor: 0,
  amount_left: "0.00",
  refundable_minor: 159800,
  refundable: "1598.00",
  payments: [
    { id: "pay1", amount_minor: 159800, amount: "1598.00", method: "upi", reference: "UTR 9", recorded_by_name: "Sam", paid_at: NOW },
  ],
});

function setup(current: Order, handlers: Record<string, (call: Call, params: Record<string, string>) => Response> = {}) {
  return renderWithApi(<OrderSheet order={current} limits={LIMITS} onOpenChange={() => undefined} />, {
    handlers: { "GET /v1/w/:wid/social-accounts/:aid/templates": () => json({ items: [] }), ...handlers },
  });
}

beforeEach(() => {
  toast.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("an order's money and shipping (GR-32 follow-ups)", () => {
  it("records a part payment by amount and says what it recorded", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    setup(order(), {
      "POST /v1/w/:wid/orders/:order_id/mark-paid": (call) => {
        bodies.push(call.body);
        return json(order({ status: "partially_paid", amount_paid_minor: 50000, amount_left_minor: 109800 }));
      },
    });
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByRole("button", { name: "Mark as paid" })).toBeInTheDocument();
    await user.type(within(sheet).getByLabelText(/Amount received/), "500");
    await user.type(within(sheet).getByLabelText(/Payment reference/), "UTR 1");
    await user.click(within(sheet).getByRole("button", { name: "Record payment" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Recorded ₹500.00 on order #12."));
    expect(bodies).toEqual([{ reference: "UTR 1", amount_minor: 50000, notice: null }]);
  });

  it("refuses an amount that isn't one before asking the server", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    setup(order(), { "POST /v1/w/:wid/orders/:order_id/mark-paid": (call) => (bodies.push(call.body), json(order())) });
    const sheet = await screen.findByRole("dialog");
    await user.type(within(sheet).getByLabelText(/Amount received/), "five hundred");
    expect(within(sheet).getByText("Enter an amount, like 500 or 499.50.")).toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "Mark as paid" }));
    expect(bodies).toEqual([]);
  });

  it("shows what is paid and left on a part-paid order, with its payments, and no cancel", async () => {
    setup(
      order({
        status: "partially_paid",
        amount_paid_minor: 50000,
        amount_paid: "500.00",
        amount_left_minor: 109800,
        amount_left: "1098.00",
        payments: [
          { id: "pay1", amount_minor: 50000, amount: "500.00", method: "upi", reference: "UTR 1", recorded_by_name: "Sam", paid_at: NOW },
        ],
      }),
    );
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByText("Partly paid")).toBeInTheDocument();
    expect(within(sheet).getByText("Paid so far")).toBeInTheDocument();
    expect(within(sheet).getByText(/₹1,098\.00/)).toBeInTheDocument();
    expect(within(sheet).getByText(/recorded by Sam. UTR 1/)).toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "Cancel order" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "Edit order" })).not.toBeInTheDocument();
  });

  it("marks a paid order shipped with a note", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    setup(PAID, {
      "POST /v1/w/:wid/orders/:order_id/fulfil": (call) => {
        bodies.push(call.body);
        return json({ ...PAID, status: "fulfilled" });
      },
    });
    const sheet = await screen.findByRole("dialog");
    await user.type(within(sheet).getByLabelText(/Shipping note/), "Delhivery 123");
    await user.click(within(sheet).getByRole("button", { name: "Mark as shipped" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Order #12 marked shipped."));
    expect(bodies).toEqual([{ note: "Delhivery 123", notice: null }]);
  });

  it("refunds only with a reason, and sends an amount only when one is typed", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    setup(PAID, {
      "POST /v1/w/:wid/orders/:order_id/refunds": (call) => {
        bodies.push(call.body);
        return json(PAID);
      },
    });
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByText(/Up to ₹1,598\.00/)).toBeInTheDocument();
    const button = within(sheet).getByRole("button", { name: "Refund" });
    expect(button).toBeDisabled();
    await user.type(within(sheet).getByLabelText("Reason"), "Damaged in transit");
    await user.click(button);
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ amount_minor: null, reason: "Damaged in transit", notice: null });

    await user.type(within(sheet).getByLabelText(/^Amount \(blank/), "300");
    await user.type(within(sheet).getByLabelText("Reason"), "x");
    await user.click(within(sheet).getByRole("button", { name: "Refund" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toMatchObject({ amount_minor: 30000 });
  });

  it("hides the refund form when nothing is left to refund and lists the refunds made", async () => {
    setup(
      order({
        ...PAID,
        status: "refunded",
        amount_refunded_minor: 159800,
        refundable_minor: 0,
        refunds: [
          {
            id: "r1",
            amount_minor: 159800,
            amount: "1598.00",
            reason: "Returned",
            method: "razorpay",
            status: "processed",
            failure: null,
            created_by_name: "Sam",
            created_at: NOW,
            processed_at: NOW,
          },
        ],
      }),
    );
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).queryByRole("button", { name: "Refund" })).not.toBeInTheDocument();
    expect(within(sheet).getByText(/Refunded. Returned/)).toBeInTheDocument();
  });

  it("says when the customer could not be messaged, and the order still changed", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    setup(PAID, {
      "POST /v1/w/:wid/orders/:order_id/fulfil": (call) => {
        bodies.push(call.body);
        return json({
          ...PAID,
          status: "fulfilled",
          notice: { sent: false, reason: "The messaging window has closed. Instagram only allows messages for 24 hours." },
        });
      },
    });
    const sheet = await screen.findByRole("dialog");
    await user.click(within(sheet).getByRole("switch", { name: "Tell the customer in the chat" }));
    await user.type(within(sheet).getByLabelText("Message to the customer"), "On its way!");
    await user.click(within(sheet).getByRole("button", { name: "Mark as shipped" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Order #12 marked shipped."));
    expect(toast).toHaveBeenCalledWith(
      "The customer wasn't messaged. The messaging window has closed. Instagram only allows messages for 24 hours.",
    );
    expect(bodies).toEqual([
      { note: null, notice: { message: "On its way!", template_name: null, template_language: null } },
    ]);
  });

  it("offers approved utility templates for a WhatsApp conversation", async () => {
    const user = userEvent.setup();
    setup(order({ ...PAID, platform: "whatsapp" }), {
      "GET /v1/w/:wid/social-accounts/:aid/templates": () =>
        json({
          items: [
            { name: "order_shipped", language: "en", category: "utility", status: "approved", body: "Hi {{1}}", param_count: 2 },
            { name: "sale_offer", language: "en", category: "marketing", status: "approved", body: "Sale", param_count: 2 },
          ],
        }),
    });
    const sheet = await screen.findByRole("dialog");
    await user.click(within(sheet).getByRole("switch", { name: "Tell the customer in the chat" }));
    const select = await within(sheet).findByLabelText("Template if the 24-hour window has closed");
    await waitFor(() => expect(within(select).getByRole("option", { name: "order_shipped (en)" })).toBeInTheDocument());
    expect(within(select).queryByRole("option", { name: /sale_offer/ })).not.toBeInTheDocument();
  });
});
