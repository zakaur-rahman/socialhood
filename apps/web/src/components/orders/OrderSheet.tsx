"use client";

import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useCancelOrder, useMarkOrderPaid, useRequestPayment } from "@/lib/api/queries";
import type { Order, OrderList, OrderPaymentMethod } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";
import {
  actionsFor,
  customerName,
  lineName,
  orderNumber,
  orderTotal,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/lib/orders/format";
import { formatDayTime } from "@/lib/tz";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const METHOD_LABEL: Record<OrderPaymentMethod, string> = { razorpay: "Razorpay", upi: "UPI" };

/**
 * One order (GR-32): its lines as they were priced, the address, how it is being paid and what a
 * member can do next. A Razorpay order is marked paid by Razorpay's webhook; a UPI order has no
 * confirmation, so the sheet says so and offers "Mark as paid" (who and when are recorded).
 */
export function OrderSheet({
  order,
  limits,
  onOpenChange,
}: {
  order: Order | null;
  limits: OrderList["limits"] | undefined;
  onOpenChange: (open: boolean) => void;
}) {
  const { id: wid, slug, timezone } = useCurrentWorkspace();
  const request = useRequestPayment(wid);
  const markPaid = useMarkOrderPaid(wid);
  const cancel = useCancelOrder(wid);
  const [reference, setReference] = useState("");

  if (!order) return <Sheet open={false} onOpenChange={onOpenChange} />;
  const can = actionsFor(order.status);
  const address = order.address
    ? [order.address.name, order.address.line1, order.address.line2, order.address.city, order.address.state, order.address.pincode]
        .filter(Boolean)
        .join(", ")
    : "";

  function pay(method: OrderPaymentMethod) {
    request.mutate(
      { orderId: (order as Order).id, method, send: true },
      {
        onSuccess: () => toast.success(method === "razorpay" ? "Payment link sent." : "UPI request sent."),
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Sheet open onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Order {orderNumber(order)}</SheetTitle>
          <SheetDescription>
            {customerName(order)} · {formatDayTime(order.created_at, timezone)}
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[order.status]}>{STATUS_LABEL[order.status]}</Badge>
            {order.payment_method ? <Badge tone="neutral">{METHOD_LABEL[order.payment_method]}</Badge> : null}
          </div>

          <ul className="divide-y divide-line rounded-lg border border-line text-sm" aria-label="Items">
            {order.items.map((line) => (
              <li key={line.id} className="flex items-start justify-between gap-3 px-3 py-2">
                <span className="min-w-0 break-words">{lineName(line)}</span>
                <span className="shrink-0">{formatPrice(line.line_total_minor, order.currency)}</span>
              </li>
            ))}
            <li className="flex items-center justify-between px-3 py-2 font-semibold">
              <span>Total</span>
              <span>{orderTotal(order)}</span>
            </li>
          </ul>

          {address ? (
            <div className="text-sm">
              <p className="font-medium">Deliver to</p>
              <p className="text-fg-secondary">{address}</p>
              {order.address?.phone ? <p className="text-fg-secondary">{order.address.phone}</p> : null}
            </div>
          ) : null}
          {order.note ? (
            <div className="text-sm">
              <p className="font-medium">Note</p>
              <p className="text-fg-secondary">{order.note}</p>
            </div>
          ) : null}

          {order.status === "paid" ? (
            <p className="text-sm text-fg-secondary">
              Paid {order.paid_at ? formatDayTime(order.paid_at, timezone) : ""}
              {order.paid_by_name ? `, marked by ${order.paid_by_name}` : order.payment_method === "razorpay" ? ", confirmed by Razorpay" : ""}
              {order.payment_reference ? `. Reference ${order.payment_reference}.` : "."}
            </p>
          ) : null}
          {order.status === "expired" ? (
            <p className="text-sm text-fg-secondary">The payment link ran out. Send a new one.</p>
          ) : null}
          {order.status === "awaiting_payment" && order.payment_method === "upi" ? (
            <p className="text-sm text-fg-secondary">
              UPI has no confirmation from the bank. When the customer says they have paid, mark the order paid.
            </p>
          ) : null}

          {can.pay ? (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={!limits?.razorpay_ready || !order.conversation_id}
                loading={request.isPending}
                onClick={() => pay("razorpay")}
              >
                {order.status === "awaiting_payment" && order.payment_method === "razorpay" ? "Send a new link" : "Send Razorpay link"}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={!limits?.upi_ready || !order.conversation_id || order.currency !== "INR"}
                loading={request.isPending}
                onClick={() => pay("upi")}
              >
                Send UPI request
              </Button>
            </div>
          ) : null}
          {can.pay && limits && !limits.razorpay_ready && !limits.upi_ready ? (
            <p className="text-xs text-fg-secondary">Set up Razorpay or UPI under Payments to send payment requests.</p>
          ) : null}

          {can.markPaid ? (
            <div className="space-y-2 border-t border-line pt-4">
              <Field id="order-reference">
                <FieldLabel>Payment reference (optional)</FieldLabel>
                <Input maxLength={200} value={reference} onChange={(e) => setReference(e.target.value)} />
              </Field>
              <Button
                size="sm"
                variant="secondary"
                loading={markPaid.isPending}
                onClick={() =>
                  markPaid.mutate(
                    { orderId: order.id, reference: reference.trim() || null },
                    {
                      onSuccess: () => {
                        setReference("");
                        toast.success(`Order ${orderNumber(order)} marked paid.`);
                      },
                      onError: (error) => toastError(error),
                    },
                  )
                }
              >
                Mark as paid
              </Button>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
            {order.conversation_id ? (
              <Button asChild variant="ghost" size="sm">
                <Link href={`/w/${slug}/inbox/${order.conversation_id}` as Route}>Open conversation</Link>
              </Button>
            ) : null}
            {can.cancel ? (
              <Button
                variant="destructive-ghost"
                size="sm"
                loading={cancel.isPending}
                onClick={() =>
                  cancel.mutate(order.id, {
                    onSuccess: () => toast.success(`Order ${orderNumber(order)} cancelled.`),
                    onError: (error) => toastError(error),
                  })
                }
              >
                Cancel order
              </Button>
            ) : null}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
