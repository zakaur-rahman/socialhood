"use client";

import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  useCancelOrder,
  useFulfilOrder,
  useMarkOrderPaid,
  useRefundOrder,
  useRequestPayment,
} from "@/lib/api/queries";
import type { Order, OrderList, OrderPaymentMethod } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";
import {
  actionsFor,
  amountMinor,
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

import { EditOrderDialog } from "./EditOrderDialog";
import { NO_NOTICE, noticeOf, noticeSentence, OrderNoticeFields, type NoticeState } from "./OrderNoticeFields";

const METHOD_LABEL: Record<OrderPaymentMethod, string> = { razorpay: "Razorpay", upi: "UPI" };
const REFUND_STATUS: Record<string, string> = { pending: "On its way", processed: "Refunded", failed: "Failed" };

/**
 * One order (GR-32): its lines as they were priced, the address, how it is being paid and what a
 * member can do next. A Razorpay order is marked paid by Razorpay's webhook; a UPI order has no
 * confirmation, so the sheet says so and offers "Mark as paid" (who and when are recorded), or a
 * part payment by amount. A paid order can be marked shipped and refunded in full or in part with
 * a reason; an unpaid one can be changed or cancelled. Each status change can also message the
 * customer in the chat (the answer says whether it went and why not).
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
  const fulfil = useFulfilOrder(wid);
  const refund = useRefundOrder(wid);
  const [reference, setReference] = useState("");
  const [amount, setAmount] = useState("");
  const [shipNote, setShipNote] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [notice, setNotice] = useState<NoticeState>(NO_NOTICE);
  const [partial, setPartial] = useState(false);
  const [editing, setEditing] = useState(false);

  if (!order) return <Sheet open={false} onOpenChange={onOpenChange} />;
  const current: Order = order;
  const can = actionsFor(current.status);
  const payments = current.payments ?? [];
  const refunds = current.refunds ?? [];
  const paidSoFar = current.amount_paid_minor ?? 0;
  const left = current.amount_left_minor ?? current.total_minor;
  const refundable = current.refundable_minor ?? 0;
  const money = (minor: number) => formatPrice(minor, current.currency);
  const address = current.address
    ? [current.address.name, current.address.line1, current.address.line2, current.address.city, current.address.state, current.address.pincode]
        .filter(Boolean)
        .join(", ")
    : "";
  const typedAmount = amount.trim() ? amountMinor(amount, current.currency) : null;
  const amountProblem = amount.trim() && typedAmount === null ? "Enter an amount, like 500 or 499.50." : null;
  const typedRefund = refundAmount.trim() ? amountMinor(refundAmount, current.currency) : null;
  const refundProblem = refundAmount.trim() && typedRefund === null ? "Enter an amount, like 500 or 499.50." : null;
  const asking = can.markPaid || can.cancel || can.ship || can.refund;

  /** The toast for a change, and a second one when the customer was asked to be messaged and wasn't. */
  function done(changed: Order, message: string) {
    toast.success(message);
    const sentence = noticeSentence(changed.notice);
    if (changed.notice && !changed.notice.sent && sentence) toast(sentence);
    else if (changed.notice?.sent) toast("The customer was messaged.");
  }

  function pay(method: OrderPaymentMethod) {
    request.mutate(
      { orderId: current.id, method, send: true, allowPartial: method === "razorpay" && partial },
      {
        onSuccess: () => toast.success(method === "razorpay" ? "Payment link sent." : "UPI request sent."),
        onError: (error) => toastError(error),
      },
    );
  }

  function recordPayment() {
    if (amountProblem) return;
    markPaid.mutate(
      { orderId: current.id, reference: reference.trim() || null, amountMinor: typedAmount, notice: noticeOf(notice) },
      {
        onSuccess: (changed) => {
          setReference("");
          setAmount("");
          done(
            changed,
            typedAmount === null
              ? `Order ${orderNumber(current)} marked paid.`
              : `Recorded ${money(typedAmount)} on order ${orderNumber(current)}.`,
          );
        },
        onError: (error) => toastError(error),
      },
    );
  }

  function ship() {
    fulfil.mutate(
      { orderId: current.id, note: shipNote.trim() || null, notice: noticeOf(notice) },
      {
        onSuccess: (changed) => {
          setShipNote("");
          done(changed, `Order ${orderNumber(current)} marked shipped.`);
        },
        onError: (error) => toastError(error),
      },
    );
  }

  function giveBack() {
    if (refundProblem || !refundReason.trim()) return;
    refund.mutate(
      { orderId: current.id, amountMinor: typedRefund, reason: refundReason.trim(), notice: noticeOf(notice) },
      {
        onSuccess: (changed) => {
          setRefundAmount("");
          setRefundReason("");
          done(changed, `Refund started for order ${orderNumber(current)}.`);
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Sheet open onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Order {orderNumber(current)}</SheetTitle>
          <SheetDescription>
            {customerName(current)} · {formatDayTime(current.created_at, timezone)}
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[current.status]}>{STATUS_LABEL[current.status]}</Badge>
            {current.payment_method ? <Badge tone="neutral">{METHOD_LABEL[current.payment_method]}</Badge> : null}
            {current.status !== "refunded" && (current.amount_refunded_minor ?? 0) > 0 ? (
              <Badge tone="neutral">Partly refunded</Badge>
            ) : null}
          </div>

          <ul className="divide-y divide-line rounded-lg border border-line text-sm" aria-label="Items">
            {current.items.map((line) => (
              <li key={line.id} className="flex items-start justify-between gap-3 px-3 py-2">
                <span className="min-w-0 break-words">{lineName(line)}</span>
                <span className="shrink-0">{formatPrice(line.line_total_minor, current.currency)}</span>
              </li>
            ))}
            <li className="flex items-center justify-between px-3 py-2 font-semibold">
              <span>Total</span>
              <span>{orderTotal(current)}</span>
            </li>
            {paidSoFar > 0 ? (
              <>
                <li className="flex items-center justify-between px-3 py-2">
                  <span>Paid so far</span>
                  <span>{money(paidSoFar)}</span>
                </li>
                {left > 0 ? (
                  <li className="flex items-center justify-between px-3 py-2">
                    <span>Left to pay</span>
                    <span>{money(left)}</span>
                  </li>
                ) : null}
              </>
            ) : null}
            {(current.amount_refunded_minor ?? 0) > 0 ? (
              <li className="flex items-center justify-between px-3 py-2">
                <span>Refunded</span>
                <span>{money(current.amount_refunded_minor ?? 0)}</span>
              </li>
            ) : null}
          </ul>

          {address ? (
            <div className="text-sm">
              <p className="font-medium">Deliver to</p>
              <p className="text-fg-secondary">{address}</p>
              {current.address?.phone ? <p className="text-fg-secondary">{current.address.phone}</p> : null}
            </div>
          ) : null}
          {current.note ? (
            <div className="text-sm">
              <p className="font-medium">Note</p>
              <p className="text-fg-secondary">{current.note}</p>
            </div>
          ) : null}

          {current.status === "paid" || current.status === "fulfilled" ? (
            <p className="text-sm text-fg-secondary">
              Paid {current.paid_at ? formatDayTime(current.paid_at, timezone) : ""}
              {current.paid_by_name ? `, marked by ${current.paid_by_name}` : current.payment_method === "razorpay" ? ", confirmed by Razorpay" : ""}
              {current.payment_reference ? `. Reference ${current.payment_reference}.` : "."}
            </p>
          ) : null}
          {current.status === "fulfilled" ? (
            <p className="text-sm text-fg-secondary">
              Shipped {current.fulfilled_at ? formatDayTime(current.fulfilled_at, timezone) : ""}
              {current.fulfilment_note ? `. ${current.fulfilment_note}` : "."}
            </p>
          ) : null}
          {current.status === "expired" ? (
            <p className="text-sm text-fg-secondary">The payment link ran out. Send a new one.</p>
          ) : null}
          {current.status === "awaiting_payment" && current.payment_method === "upi" ? (
            <p className="text-sm text-fg-secondary">
              UPI has no confirmation from the bank. When the customer says they have paid, mark the order paid.
            </p>
          ) : null}

          {payments.length > 0 ? (
            <section aria-labelledby="order-payments" className="space-y-1.5">
              <h3 id="order-payments" className="text-sm font-medium">
                Payments
              </h3>
              <ul className="divide-y divide-line rounded-lg border border-line text-sm">
                {payments.map((payment) => (
                  <li key={payment.id} className="flex items-start justify-between gap-3 px-3 py-2">
                    <span className="min-w-0 break-words">
                      {METHOD_LABEL[payment.method]}, {formatDayTime(payment.paid_at, timezone)}
                      {payment.recorded_by_name ? `, recorded by ${payment.recorded_by_name}` : ""}
                      {payment.reference ? `. ${payment.reference}` : ""}
                    </span>
                    <span className="shrink-0">{money(payment.amount_minor)}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {refunds.length > 0 ? (
            <section aria-labelledby="order-refunds" className="space-y-1.5">
              <h3 id="order-refunds" className="text-sm font-medium">
                Refunds
              </h3>
              <ul className="divide-y divide-line rounded-lg border border-line text-sm">
                {refunds.map((item) => (
                  <li key={item.id} className="flex items-start justify-between gap-3 px-3 py-2">
                    <span className="min-w-0 break-words">
                      {REFUND_STATUS[item.status] ?? item.status}
                      {item.method === "manual" ? ", paid back by you" : ""}. {item.reason}
                      {item.failure ? ` ${item.failure}` : ""}
                      {item.created_by_name ? ` (${item.created_by_name})` : ""}
                    </span>
                    <span className="shrink-0">{money(item.amount_minor)}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {can.pay ? (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={!limits?.razorpay_ready || !current.conversation_id}
                  loading={request.isPending}
                  onClick={() => pay("razorpay")}
                >
                  {current.status === "awaiting_payment" && current.payment_method === "razorpay" ? "Send a new link" : "Send Razorpay link"}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!limits?.upi_ready || !current.conversation_id || current.currency !== "INR"}
                  loading={request.isPending}
                  onClick={() => pay("upi")}
                >
                  Send UPI request
                </Button>
              </div>
              {current.currency === "INR" && limits?.razorpay_ready ? (
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={partial} onCheckedChange={(on) => setPartial(on === true)} />
                  Let them pay the Razorpay link in parts
                </label>
              ) : null}
            </div>
          ) : null}
          {can.pay && limits && !limits.razorpay_ready && !limits.upi_ready ? (
            <p className="text-xs text-fg-secondary">Set up Razorpay or UPI under Payments to send payment requests.</p>
          ) : null}

          {asking ? (
            <div className="space-y-4 border-t border-line pt-4">
              <OrderNoticeFields order={current} value={notice} onChange={setNotice} />

              {can.markPaid ? (
                <div className="space-y-2">
                  <Field id="order-amount">
                    <FieldLabel>Amount received (blank for everything left)</FieldLabel>
                    <Input
                      inputMode="decimal"
                      maxLength={20}
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      aria-invalid={amountProblem ? true : undefined}
                    />
                    {amountProblem ? <p className="text-xs text-danger-fg">{amountProblem}</p> : null}
                  </Field>
                  <Field id="order-reference">
                    <FieldLabel>Payment reference (optional)</FieldLabel>
                    <Input maxLength={200} value={reference} onChange={(e) => setReference(e.target.value)} />
                  </Field>
                  <Button size="sm" variant="secondary" loading={markPaid.isPending} onClick={recordPayment}>
                    {typedAmount === null ? "Mark as paid" : "Record payment"}
                  </Button>
                </div>
              ) : null}

              {can.ship ? (
                <div className="space-y-2">
                  <Field id="order-ship-note">
                    <FieldLabel>Shipping note (optional)</FieldLabel>
                    <Input
                      maxLength={300}
                      value={shipNote}
                      onChange={(e) => setShipNote(e.target.value)}
                      placeholder="Courier and tracking number"
                    />
                  </Field>
                  <Button size="sm" variant="secondary" loading={fulfil.isPending} onClick={ship}>
                    Mark as shipped
                  </Button>
                </div>
              ) : null}

              {can.refund && refundable > 0 ? (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Refund</h3>
                  <p className="text-xs text-fg-secondary">
                    Up to {money(refundable)}. A Razorpay payment goes back through your Razorpay account. A UPI payment
                    can&rsquo;t be sent back from here: pay it back yourself, then record it.
                  </p>
                  <Field id="order-refund-amount">
                    <FieldLabel>Amount (blank for everything)</FieldLabel>
                    <Input
                      inputMode="decimal"
                      maxLength={20}
                      value={refundAmount}
                      onChange={(e) => setRefundAmount(e.target.value)}
                      aria-invalid={refundProblem ? true : undefined}
                    />
                    {refundProblem ? <p className="text-xs text-danger-fg">{refundProblem}</p> : null}
                  </Field>
                  <Field id="order-refund-reason">
                    <FieldLabel>Reason</FieldLabel>
                    <Input maxLength={200} value={refundReason} onChange={(e) => setRefundReason(e.target.value)} />
                  </Field>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!refundReason.trim() || Boolean(refundProblem)}
                    loading={refund.isPending}
                    onClick={giveBack}
                  >
                    Refund
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
            {current.conversation_id ? (
              <Button asChild variant="ghost" size="sm">
                <Link href={`/w/${slug}/inbox/${current.conversation_id}` as Route}>Open conversation</Link>
              </Button>
            ) : null}
            {can.edit ? (
              <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                Edit order
              </Button>
            ) : null}
            {can.cancel ? (
              <Button
                variant="destructive-ghost"
                size="sm"
                loading={cancel.isPending}
                onClick={() =>
                  cancel.mutate(
                    { orderId: current.id, notice: noticeOf(notice) },
                    {
                      onSuccess: (changed) => done(changed, `Order ${orderNumber(current)} cancelled.`),
                      onError: (error) => toastError(error),
                    },
                  )
                }
              >
                Cancel order
              </Button>
            ) : null}
          </div>
        </div>
        {editing ? <EditOrderDialog key={current.updated_at} order={current} open onOpenChange={setEditing} /> : null}
      </SheetContent>
    </Sheet>
  );
}
