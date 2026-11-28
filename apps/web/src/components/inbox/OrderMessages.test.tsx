import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReplyInput } from "@/lib/api/queries";
import type { Message, Order, OrderList } from "@/lib/api/types";
import { json, message, problem, renderWithApi, type Call } from "@/test/api";

import { ADDRESS_ASK, AddressBar, OrderCard, useOrderReply } from "./OrderMessages";

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const NOW = "2026-11-28T10:00:00Z";

function line(n: number, values: Partial<Order["items"][number]> = {}): Order["items"][number] {
  return {
    id: `l${n}`,
    product_id: `p${n}`,
    variant_id: null,
    name: `Product ${n}`,
    variant_title: null,
    sku: null,
    quantity: 1,
    unit_price_minor: 10000,
    unit_price: "100.00",
    line_total_minor: 10000,
    line_total: "100.00",
    ...values,
  };
}

function order(values: Partial<Order> = {}): Order {
  return {
    id: "o1",
    number: 1,
    status: "awaiting_payment",
    source: "whatsapp",
    currency: "INR",
    total_minor: 249900,
    total: "2499.00",
    items: [line(1, { name: "Handloom Saree", unit_price_minor: 249900, line_total_minor: 249900 })],
    address: null,
    note: null,
    contact: { id: "p1", display_name: "Priya Shah", username: null },
    conversation_id: "c1",
    social_account_id: "a1",
    platform: "whatsapp",
    payment_method: null,
    payment_link_url: null,
    payment_reference: null,
    link_expires_at: null,
    paid_at: null,
    paid_by_name: null,
    cancelled_at: null,
    created_by_name: null,
    created_at: NOW,
    updated_at: NOW,
    amount_paid_minor: 0,
    amount_paid: "0.00",
    amount_left_minor: 249900,
    amount_left: "2499.00",
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

const ADDRESS = {
  name: "Priya Shah",
  phone: null,
  line1: "12 MG Road",
  line2: "Indiranagar",
  city: "Bengaluru",
  state: "Karnataka",
  pincode: "560038",
  country: "India",
};

function handlers(current: Order | null, limits: Partial<OrderList["limits"]> = {}) {
  return {
    "GET /v1/w/:wid/orders/:id": () => (current ? json(current) : problem(404, "not_found", "No such order.")),
    "GET /v1/w/:wid/orders": () =>
      json({ items: [], total: 0, limits: { entitled: true, razorpay_ready: false, upi_ready: false, ...limits } }),
    "POST /v1/w/:wid/orders/:id/payment-request": () => json(current),
  };
}

const cart = message({ id: "m1", text: "Order #1: 1 x Handloom Saree, 2,499.00 INR in total", order: { id: "o1", number: 1 } });

function Reply({ messages, onSend }: { messages: Message[]; onSend: (input: ReplyInput) => void }) {
  return <>{useOrderReply({ messages, canReply: true, onSend })}</>;
}

beforeEach(() => {
  toast.success.mockReset();
  toast.error.mockReset();
});

describe("OrderCard (C-218)", () => {
  it("lists five lines, then 'and N more', the total and that no address was given", async () => {
    const items = Array.from({ length: 7 }, (_, i) => line(i + 1, { quantity: 2, line_total_minor: 20000 }));
    renderWithApi(<OrderCard orderId="o1" text="Order #1: 14 items" />, {
      handlers: handlers(order({ items, total_minor: 140000 }), { razorpay_ready: true }),
    });
    const card = await screen.findByTestId("order-card");
    expect(within(card).getByText("Order #1")).toBeInTheDocument();
    expect(within(card).getByText("Waiting for payment")).toBeInTheDocument();
    const lines = within(within(card).getByRole("list", { name: "Items" })).getAllByRole("listitem");
    expect(lines).toHaveLength(6);
    expect(lines[0]).toHaveTextContent("2 x Product 1₹200.00");
    expect(lines[5]).toHaveTextContent("and 2 more");
    expect(within(card).getByText("₹1,400.00")).toBeInTheDocument();
    expect(within(card).getByText("Delivery address: Not given yet")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "View order" })).toHaveAttribute("href", "/w/maple/orders?order=o1");
    expect(await within(card).findByRole("button", { name: "Request payment" })).toBeInTheDocument();
  });

  it("shows the address in two lines, and no Request payment for a paid order", async () => {
    renderWithApi(<OrderCard orderId="o1" text={null} />, {
      handlers: handlers(order({ address: ADDRESS, status: "paid" }), { razorpay_ready: true }),
    });
    const card = await screen.findByTestId("order-card");
    expect(within(card).getByText("Priya Shah, 12 MG Road, Indiranagar")).toBeInTheDocument();
    expect(within(card).getByText("Bengaluru, Karnataka, 560038, India")).toBeInTheDocument();
    expect(within(card).getByText("Paid")).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "Request payment" })).not.toBeInTheDocument();
  });

  it("falls back to the message text when the order can't be loaded", async () => {
    renderWithApi(<OrderCard orderId="o1" text="Order #1: 1 x Handloom Saree, 2,499.00 INR in total" />, {
      handlers: handlers(null),
    });
    expect(await screen.findByText("Order #1: 1 x Handloom Saree, 2,499.00 INR in total")).toBeInTheDocument();
    expect(screen.queryByTestId("order-card")).not.toBeInTheDocument();
  });
});

describe("Order reply bar (C-218)", () => {
  it("previews the confirmation with the address request; Send confirmation sends that text", async () => {
    const onSend = vi.fn();
    renderWithApi(<Reply messages={[cart]} onSend={onSend} />, { handlers: handlers(order()) });
    const text = await screen.findByTestId("order-reply-text");
    const expected = `Thanks for your order! Order #1\n1 x Handloom Saree: ₹2,499.00\nTotal: ₹2,499.00\n\n${ADDRESS_ASK}`;
    expect(text.textContent).toBe(expected);
    // Neither Razorpay nor UPI is set up: no payment link button.
    await waitFor(() => expect(screen.getByRole("button", { name: "Send confirmation" })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Send with payment link" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Send confirmation" }));
    expect(onSend).toHaveBeenCalledWith({ text: expected });
    expect(screen.queryByTestId("order-reply-text")).not.toBeInTheDocument();
  });

  it("leaves out the address request when the order has one", async () => {
    renderWithApi(<Reply messages={[cart]} onSend={vi.fn()} />, { handlers: handlers(order({ address: ADDRESS })) });
    expect((await screen.findByTestId("order-reply-text")).textContent).toBe(
      "Thanks for your order! Order #1\n1 x Handloom Saree: ₹2,499.00\nTotal: ₹2,499.00",
    );
  });

  it("sends the payment link with Razorpay first, asking for the address", async () => {
    const { calls } = renderWithApi(<Reply messages={[cart]} onSend={vi.fn()} />, {
      handlers: handlers(order(), { razorpay_ready: true, upi_ready: true }),
    });
    await userEvent.click(await screen.findByRole("button", { name: "Send with payment link" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Payment link sent."));
    const request = calls.find((c) => c.method === "POST" && c.path.endsWith("/payment-request"));
    expect(request?.path).toBe("/v1/w/w1/orders/o1/payment-request");
    expect(request?.body).toEqual({ method: "razorpay", send: true, allow_partial: false, ask_address: true });
  });

  it("uses UPI when only UPI is set up", async () => {
    const { calls } = renderWithApi(<Reply messages={[cart]} onSend={vi.fn()} />, {
      handlers: handlers(order({ address: ADDRESS }), { upi_ready: true }),
    });
    await userEvent.click(await screen.findByRole("button", { name: "Send with payment link" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("UPI request sent."));
    const request = calls.find((c) => c.path.endsWith("/payment-request"));
    expect(request?.body).toMatchObject({ method: "upi", ask_address: false });
  });

  it("stays away for an order that isn't waiting for payment, or when the cart isn't the latest message", async () => {
    // The card shares the order's query: once it shows, the bar has the order too.
    renderWithApi(
      <>
        <OrderCard orderId="o1" text={null} />
        <Reply messages={[cart]} onSend={vi.fn()} />
      </>,
      { handlers: handlers(order({ status: "paid" })) },
    );
    await screen.findByTestId("order-card");
    expect(screen.queryByTestId("order-reply-text")).not.toBeInTheDocument();
  });

  it("stays away when the cart isn't the latest message", async () => {
    renderWithApi(
      <>
        <OrderCard orderId="o1" text={null} />
        <Reply messages={[cart, message({ id: "m2", direction: "outbound", source: "human", text: "Thanks!" })]} onSend={vi.fn()} />
      </>,
      { handlers: handlers(order()) },
    );
    await screen.findByTestId("order-card");
    expect(screen.queryByTestId("order-reply-text")).not.toBeInTheDocument();
  });
});

describe("Address bar (C-218)", () => {
  const reply = message({ id: "m2", text: "Priya Shah, 12 MG Road, Indiranagar, Bengaluru 560038" });

  it("reads the address into the form and saves it on the order", async () => {
    const { calls } = renderWithApi(<AddressBar messages={[cart, reply]} />, {
      handlers: {
        ...handlers(order()),
        "POST /v1/w/:wid/orders/:id/address/read": () => json({ found: true, address: { ...ADDRESS, country: null } }),
        "PATCH /v1/w/:wid/orders/:id": (call: Call) => json(order({ address: (call.body as { address: Order["address"] }).address })),
      },
    });
    expect(await screen.findByText("Is this the delivery address for Order #1?")).toBeInTheDocument();
    expect(screen.getByText("1 AI credit")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Read address" }));

    expect(await screen.findByLabelText("Name")).toHaveValue("Priya Shah");
    expect(screen.getByLabelText("Pincode")).toHaveValue("560038");
    expect(calls.find((c) => c.path.endsWith("/address/read"))?.body).toEqual({ message_id: "m2" });

    await userEvent.type(screen.getByLabelText("Country"), "India");
    await userEvent.click(screen.getByRole("button", { name: "Save address" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Delivery address saved for Order #1"));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ address: ADDRESS_FILLED });
    await waitFor(() => expect(screen.queryByText(/delivery address for Order #1/)).not.toBeInTheDocument());
  });

  it("says when there is no address in the message, and lets the member type it in", async () => {
    renderWithApi(<AddressBar messages={[cart, reply]} />, {
      handlers: {
        ...handlers(order()),
        "POST /v1/w/:wid/orders/:id/address/read": () =>
          json({ found: false, address: { name: null, phone: null, line1: null, line2: null, city: null, state: null, pincode: null, country: null } }),
      },
    });
    await userEvent.click(await screen.findByRole("button", { name: "Read address" }));
    expect(await screen.findByText("No address in this message")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Type it in" }));
    expect(screen.getByLabelText("Name")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Save address" })).toBeDisabled();
  });

  it("doesn't show for an order that has an address", async () => {
    renderWithApi(
      <>
        <OrderCard orderId="o1" text={null} />
        <AddressBar messages={[cart, reply]} />
      </>,
      { handlers: handlers(order({ address: ADDRESS })) },
    );
    await screen.findByTestId("order-card");
    expect(screen.queryByText(/delivery address for Order/)).not.toBeInTheDocument();
  });
});

const ADDRESS_FILLED = {
  name: "Priya Shah",
  line1: "12 MG Road",
  line2: "Indiranagar",
  city: "Bengaluru",
  state: "Karnataka",
  pincode: "560038",
  country: "India",
};
