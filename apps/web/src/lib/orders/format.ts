import type { Order, OrderStatus } from "@/lib/api/types";
import { formatPrice, parsePrice } from "@/lib/catalogue/format";

export const STATUS_LABEL: Record<OrderStatus, string> = {
  draft: "Draft",
  awaiting_payment: "Waiting for payment",
  partially_paid: "Partly paid",
  paid: "Paid",
  fulfilled: "Shipped",
  refunded: "Refunded",
  cancelled: "Cancelled",
  expired: "Expired",
};

export const STATUS_TONE: Record<OrderStatus, "neutral" | "brand" | "success" | "warning" | "danger"> = {
  draft: "neutral",
  awaiting_payment: "brand",
  partially_paid: "warning",
  paid: "success",
  fulfilled: "success",
  refunded: "neutral",
  cancelled: "neutral",
  expired: "warning",
};

/** "#12". */
export function orderNumber(order: Pick<Order, "number">): string {
  return `#${order.number}`;
}

export function orderTotal(order: Pick<Order, "total_minor" | "currency">): string {
  return formatPrice(order.total_minor, order.currency);
}

/** "2 x Cotton kurta - Blue / M". */
export function lineName(line: Pick<Order["items"][number], "name" | "variant_title" | "quantity">): string {
  return `${line.quantity} x ${line.name}${line.variant_title ? ` - ${line.variant_title}` : ""}`;
}

/** The customer, as the inbox names them. */
export function customerName(order: Pick<Order, "contact">): string {
  const { display_name: name, username } = order.contact;
  return name || (username ? `@${username}` : "Customer");
}

export type OrderActions = {
  pay: boolean;
  markPaid: boolean;
  cancel: boolean;
  edit: boolean;
  ship: boolean;
  refund: boolean;
};

/**
 * What a member can do next with an order in this state: ask for payment or record one until it is
 * paid, edit and cancel until someone has paid, ship once it is paid, refund once there is a payment.
 */
export function actionsFor(status: OrderStatus): OrderActions {
  switch (status) {
    case "draft":
    case "awaiting_payment":
      return { pay: true, markPaid: true, cancel: true, edit: true, ship: false, refund: false };
    case "expired":
      return { pay: true, markPaid: true, cancel: false, edit: false, ship: false, refund: false };
    case "partially_paid":
      return { pay: true, markPaid: true, cancel: false, edit: false, ship: false, refund: true };
    case "paid":
      return { pay: false, markPaid: false, cancel: false, edit: false, ship: true, refund: true };
    case "fulfilled":
      return { pay: false, markPaid: false, cancel: false, edit: false, ship: false, refund: true };
    default:
      return { pay: false, markPaid: false, cancel: false, edit: false, ship: false, refund: false };
  }
}

/** Minor units from what a member typed ("500", "1,598.50"), or null when it isn't an amount. */
export function amountMinor(text: string, currency: string): number | null {
  const parsed = parsePrice(text, currency);
  if (parsed === null) return null;
  const minor = Math.round(Number(parsed) * 10 ** fractionDigits(currency));
  return Number.isFinite(minor) && minor > 0 ? minor : null;
}

function fractionDigits(currency: string): number {
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
  } catch {
    return 2;
  }
}
