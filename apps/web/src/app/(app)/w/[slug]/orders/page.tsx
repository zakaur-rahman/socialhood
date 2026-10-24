import type { Metadata } from "next";

import { OrdersPage } from "@/components/orders/OrdersPage";

export const metadata: Metadata = { title: "Orders" };

/** GR-32: orders and payment requests. */
export default function OrdersRoute() {
  return <OrdersPage />;
}
