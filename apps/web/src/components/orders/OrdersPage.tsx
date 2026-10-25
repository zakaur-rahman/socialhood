"use client";

import { Receipt } from "lucide-react";
import { useState } from "react";

import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBleed } from "@/components/ui/card";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useUpgradeDialog } from "@/lib/api/provider";
import { useOrders } from "@/lib/api/queries";
import type { OrderStatus } from "@/lib/api/types";
import { customerName, lineName, orderNumber, orderTotal, STATUS_LABEL, STATUS_TONE } from "@/lib/orders/format";
import { formatDayTime } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";

import { OrderSheet } from "./OrderSheet";
import { PaymentsCard } from "./PaymentsCard";
import { SkeletonRegion, TableSkeleton } from "@/components/states/skeletons";

type Filter = "all" | OrderStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All orders" },
  { value: "awaiting_payment", label: "Waiting for payment" },
  { value: "partially_paid", label: "Partly paid" },
  { value: "paid", label: "Paid" },
  { value: "fulfilled", label: "Shipped" },
  { value: "refunded", label: "Refunded" },
  { value: "draft", label: "Drafts" },
  { value: "expired", label: "Expired" },
  { value: "cancelled", label: "Cancelled" },
];

/**
 * Orders (GR-32, under Engage): the orders made in conversations, with their status and total, and
 * the payment settings for owners and admins. Orders are made from a conversation in the inbox
 * ("Create order"); here they are followed up: ask for payment, record a payment, ship, refund, change or cancel.
 * Reading is on every plan; making orders is part of Pro (PD-8) and the page says so.
 */
export function OrdersPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const upgrade = useUpgradeDialog();
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const orders = useOrders(wid, filter === "all" ? null : filter);
  const items = orders.data?.items ?? [];
  const limits = orders.data?.limits;
  const entitled = limits?.entitled ?? true;
  const manager = workspace.role === "owner" || workspace.role === "admin";
  const open = items.find((item) => item.id === openId) ?? null;

  return (
    <PageFrame title="Orders">
      <div className="space-y-6">
        <Card asChild padding="roomy">
          <section aria-labelledby="orders-title">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <h2 id="orders-title" className="text-base font-semibold">
                  Orders
                </h2>
                <p className="text-sm text-fg-secondary">
                  Make an order from a conversation: open it in the inbox, then More, Create order.
                  {orders.data ? ` ${orders.data.total} ${orders.data.total === 1 ? "order" : "orders"}.` : ""}
                </p>
              </div>
              <div>
                <label className="sr-only" htmlFor="order-filter">
                  Show
                </label>
                <select
                  id="order-filter"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value as Filter)}
                  className="h-9 rounded-lg border border-line-strong bg-field px-2 text-sm"
                >
                  {FILTERS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {!entitled ? (
              <Alert tone="brand" className="mt-4">
                Orders and payment requests are part of Pro. You can see what is here, but making orders needs Pro.{" "}
                {manager ? (
                  <button type="button" className="underline underline-offset-4" onClick={() => upgrade.open(COMMERCE_UPGRADE)}>
                    See plans
                  </button>
                ) : null}
              </Alert>
            ) : null}

            <CardBleed className="mt-5 border-t border-line">
              {orders.isPending ? (
                <SkeletonRegion label="Loading orders">
                  <TableSkeleton columns={6} rows={7} />
                </SkeletonRegion>
              ) : orders.isError ? (
                <div className="p-(--card-padding)">
                  <ErrorState error={orders.error} onRetry={() => void orders.refetch()} />
                </div>
              ) : items.length === 0 ? (
                <div className="p-(--card-padding)">
                  <EmptyState
                    icon={<Receipt />}
                    title={filter === "all" ? "No orders yet" : "No orders here"}
                    body={
                      filter === "all"
                        ? "When a customer is ready to buy, create an order in their conversation and send a payment link."
                        : "Try another filter."
                    }
                  />
                </div>
              ) : (
                <Table scrollLabel="Orders">
                  <TableCaption className="sr-only">Orders, newest first</TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Order</TableHead>
                      <TableHead>Customer</TableHead>
                      <TableHead>Items</TableHead>
                      <TableHead>Total</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="w-24">
                        <span className="sr-only">Actions</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((order) => (
                      <TableRow key={order.id} data-testid="order-row">
                        <TableCell className="whitespace-nowrap">
                          <p className="font-medium">{orderNumber(order)}</p>
                          <p className="text-xs text-fg-secondary">{formatDayTime(order.created_at, workspace.timezone)}</p>
                        </TableCell>
                        <TableCell>{customerName(order)}</TableCell>
                        <TableCell className="min-w-48 text-fg-secondary">
                          {order.items.slice(0, 2).map(lineName).join(", ")}
                          {order.items.length > 2 ? ` and ${order.items.length - 2} more` : ""}
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{orderTotal(order)}</TableCell>
                        <TableCell>
                          <Badge tone={STATUS_TONE[order.status]}>{STATUS_LABEL[order.status]}</Badge>
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="sm" onClick={() => setOpenId(order.id)}>
                            Open
                            <span className="sr-only"> order {orderNumber(order)}</span>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardBleed>
          </section>
        </Card>

        {/* After the orders: the card is taller once its settings load, and nothing is below it to move. */}
        {manager ? <PaymentsCard wid={wid} /> : null}
      </div>

      <OrderSheet order={open} limits={limits} onOpenChange={(next) => (next ? undefined : setOpenId(null))} />
    </PageFrame>
  );
}
