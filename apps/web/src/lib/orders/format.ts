import type { Order, OrderStatus } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";

export const STATUS_LABEL: Record<OrderStatus, string> = {
  draft: "Draft",
  awaiting_payment: "Waiting for payment",
  paid: "Paid",
  cancelled: "Cancelled",
  expired: "Expired",
};

export const STATUS_TONE: Record<OrderStatus, "neutral" | "brand" | "success" | "warning" | "danger"> = {
  draft: "neutral",
  awaiting_payment: "brand",
  paid: "success",
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

/** What a member can do next with an order in this state. */
export function actionsFor(status: OrderStatus): { pay: boolean; markPaid: boolean; cancel: boolean } {
  switch (status) {
    case "draft":
      return { pay: true, markPaid: true, cancel: true };
    case "awaiting_payment":
      return { pay: true, markPaid: true, cancel: true };
    case "expired":
      return { pay: true, markPaid: true, cancel: false };
    default:
      return { pay: false, markPaid: false, cancel: false };
  }
}
