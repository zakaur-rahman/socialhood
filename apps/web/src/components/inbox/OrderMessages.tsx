"use client";

import { MapPin, Receipt, X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { BAR } from "@/components/ai/SuggestionCard";
import { AddressFields, filledAddress } from "@/components/orders/OrderLinesFields";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cardVariants } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useEditOrder, useOrder, useOrders, useReadOrderAddress, useRequestPayment, type ReplyInput } from "@/lib/api/queries";
import type { Message, Order, OrderStatus } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";
import { actionsFor, lineName, orderNumber, orderTotal, STATUS_LABEL, STATUS_TONE } from "@/lib/orders/format";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

/** As the API words it when a payment request asks for the address (services/orders/orders.py ADDRESS_ASK). */
export const ADDRESS_ASK = "Please reply with your delivery address: name, house and street, area, city and PIN code.";

/** The card lists this many lines, then "and N more". */
const CARD_LINES = 5;

/** C-218: the confirmation "Send confirmation" sends, built from the order rather than worded by the AI. */
/** C-218: the address can still be saved once the order is paid (customers often pay first). */
const ADDRESS_STATUSES = new Set<OrderStatus>(["draft", "awaiting_payment", "partially_paid", "paid", "fulfilled"]);

export function confirmationText(order: Order): string {
  const money = (minor: number) => formatPrice(minor, order.currency);
  const text = [
    `Thanks for your order! Order ${orderNumber(order)}`,
    ...order.items.map((line) => `${lineName(line)}: ${money(line.line_total_minor)}`),
    `Total: ${money(order.total_minor)}`,
  ].join("\n");
  return order.address ? text : `${text}\n\n${ADDRESS_ASK}`;
}

/** The address in one or two lines: who and where, then the city and PIN code. */
function addressLines(address: Order["address"]): string[] {
  if (!address) return [];
  const { name, line1, line2, city, state, pincode, country } = address;
  return [[name, line1, line2], [city, state, pincode, country]]
    .map((parts) => parts.filter(Boolean).join(", "))
    .filter(Boolean);
}

/** The latest message a person wrote (system notes skipped). */
function latest(messages: Message[]): Message | null {
  for (let i = messages.length - 1; i >= 0; i--) if (messages[i].direction !== "system") return messages[i];
  return null;
}

/** Sends the order's payment request in its conversation: Razorpay when it is set up, else UPI, else none. */
function usePaymentLink(wid: string, enabled: boolean) {
  // Every member can read the orders' limits; the payment settings are for owners and admins only.
  const limits = useOrders(wid, null, enabled).data?.limits;
  const method = limits?.razorpay_ready ? "razorpay" : limits?.upi_ready ? "upi" : null;
  const request = useRequestPayment(wid);
  const send = (order: Order, onSent?: () => void) => {
    if (!method) return;
    request.mutate(
      { orderId: order.id, method, send: true, askAddress: !order.address },
      {
        onSuccess: () => {
          toast.success(method === "razorpay" ? "Payment link sent." : "UPI request sent.");
          onSent?.();
        },
        onError: (error) => toastError(error),
      },
    );
  };
  return { method, send, pending: request.isPending };
}

/**
 * C-218 in a customer's bubble: the order their WhatsApp cart became, live from the order. Falls
 * back to the message's text when the order can't be loaded (deleted, say).
 */
export function OrderCard({ orderId, text }: { orderId: string; text: string | null }) {
  const { id: wid, slug } = useCurrentWorkspace();
  const query = useOrder(wid, orderId);
  const order = query.data;
  const canPay = order ? actionsFor(order.status).pay : false;
  const pay = usePaymentLink(wid, canPay);

  if (query.isPending) {
    return (
      <div role="status" aria-label="Loading order" className="flex w-56 max-w-full flex-col gap-2 py-1">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-32" />
      </div>
    );
  }
  if (!order) return text ? <p>{text}</p> : null;

  const shown = order.items.slice(0, CARD_LINES);
  const more = order.items.length - shown.length;
  const address = addressLines(order.address);
  return (
    <div className="flex w-64 max-w-full flex-col gap-2 whitespace-normal" data-testid="order-card">
      <div className="flex items-center justify-between gap-3">
        <p className="font-medium">Order {orderNumber(order)}</p>
        <Badge tone={STATUS_TONE[order.status]}>{STATUS_LABEL[order.status]}</Badge>
      </div>
      <ul aria-label="Items" className="flex flex-col gap-0.5">
        {shown.map((line) => (
          <li key={line.id} className="flex justify-between gap-3">
            <span className="min-w-0">{lineName(line)}</span>
            <span className="shrink-0 tabular-nums">{formatPrice(line.line_total_minor, order.currency)}</span>
          </li>
        ))}
        {more > 0 ? <li className="text-fg-secondary">and {more} more</li> : null}
      </ul>
      <p className="flex justify-between gap-3 border-t border-line-subtle pt-1.5 font-medium">
        <span>Total</span>
        <span className="tabular-nums">{orderTotal(order)}</span>
      </p>
      <div className="text-xs text-fg-secondary">
        {address.length > 0 ? (
          <>
            <p>Delivery address:</p>
            {address.map((line) => (
              <p key={line} className="text-fg">
                {line}
              </p>
            ))}
          </>
        ) : (
          <p>Delivery address: Not given yet</p>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Button variant="secondary" size="xs" asChild>
          <Link href={`/w/${slug}/orders?order=${order.id}` as Route}>View order</Link>
        </Button>
        {canPay && pay.method ? (
          <Button size="xs" loading={pay.pending} onClick={() => pay.send(order)}>
            Request payment
          </Button>
        ) : null}
      </div>
    </div>
  );
}

/**
 * C-218 above the composer, in the AI draft's place: when the customer's latest message is a cart
 * that is waiting for payment, the confirmation built from the order, sent as is or with the
 * payment link. Null when it doesn't apply, so the thread shows the AI draft instead.
 */
export function useOrderReply({
  messages,
  canReply,
  onSend,
}: {
  messages: Message[];
  canReply: boolean;
  onSend: (input: ReplyInput) => void;
}): ReactNode {
  const { id: wid } = useCurrentWorkspace();
  const last = latest(messages);
  const ref = last?.direction === "inbound" ? (last.order ?? null) : null;
  const order = useOrder(wid, ref?.id ?? null).data;
  const pay = usePaymentLink(wid, ref !== null);
  const [doneFor, setDoneFor] = useState<string | null>(null);

  if (!last || !ref || !order || order.status !== "awaiting_payment" || !canReply || doneFor === last.id) return null;
  const done = () => setDoneFor(last.id);
  const text = confirmationText(order);
  return (
    <section
      aria-label={`Reply to order ${orderNumber(order)}`}
      className={cn(BAR, cardVariants({ tone: "brand" }), "rounded-lg px-3 py-2")}
    >
      <div className="flex items-start gap-2">
        <Receipt className="mt-0.5 size-3.5 shrink-0 text-brand-fg" aria-hidden />
        <p className="min-w-0 flex-1 text-sm break-words whitespace-pre-wrap text-fg" data-testid="order-reply-text">
          {text}
        </p>
        <Button variant="ghost" size="icon-sm" aria-label="Dismiss order reply" className="-my-1 text-fg-secondary" onClick={done}>
          <X aria-hidden />
        </Button>
      </div>
      <div className="mt-1.5 flex flex-wrap justify-end gap-1.5">
        <Button
          size="sm"
          variant={pay.method ? "secondary" : "default"}
          onClick={() => {
            onSend({ text });
            done();
          }}
        >
          Send confirmation
        </Button>
        {pay.method ? (
          <Button size="sm" loading={pay.pending} onClick={() => pay.send(order, done)}>
            Send with payment link
          </Button>
        ) : null}
      </div>
    </section>
  );
}

/**
 * C-218 above the composer: the customer answered with text after their order, which has no
 * address yet. The AI reads the message into the address fields (1 credit), the member checks
 * them and saves them on the order. Only for orders that can still be changed (draft or waiting).
 */
export function AddressBar({ messages }: { messages: Message[] }) {
  const { id: wid } = useCurrentWorkspace();
  const last = latest(messages);
  const reply = last?.direction === "inbound" && !last.order && last.kind === "text" && last.text ? last : null;
  let ref: Message["order"] = null;
  if (reply) for (let i = messages.length - 1; i >= 0 && !ref; i--) ref = messages[i].order ?? null;
  const order = useOrder(wid, ref?.id ?? null).data;
  const [doneFor, setDoneFor] = useState<string | null>(null);

  if (!reply || !order || order.address || !ADDRESS_STATUSES.has(order.status) || doneFor === reply.id) return null;
  return <AddressReader key={reply.id} order={order} messageId={reply.id} onDone={() => setDoneFor(reply.id)} />;
}

function AddressReader({ order, messageId, onDone }: { order: Order; messageId: string; onDone: () => void }) {
  const { id: wid } = useCurrentWorkspace();
  const read = useReadOrderAddress(wid);
  const edit = useEditOrder(wid);
  const [notFound, setNotFound] = useState(false);
  const [editing, setEditing] = useState(false);
  const [address, setAddress] = useState<Record<string, string>>({});
  const number = orderNumber(order);

  const readAddress = () =>
    read.mutate(
      { orderId: order.id, messageId },
      {
        onSuccess: (reading) => {
          if (!reading.found) return setNotFound(true);
          setEditing(true);
          setAddress(
            Object.fromEntries(
              Object.entries(reading.address).filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1] !== ""),
            ),
          );
        },
        onError: (error) => toastError(error), // out of credits (402): the upgrade dialog says so
      },
    );

  const save = (event: FormEvent) => {
    event.preventDefault();
    edit.mutate(
      { orderId: order.id, body: { address: filledAddress(address) } },
      {
        onSuccess: () => {
          toast.success(`Delivery address saved for Order ${number}`);
          onDone();
        },
        onError: (error) => toastError(error),
      },
    );
  };

  return (
    <section aria-label={`Delivery address for order ${number}`} className={cn(BAR, cardVariants(), "rounded-lg px-3 py-2")}>
      <div className="flex items-center gap-2">
        <MapPin className="size-3.5 shrink-0 text-fg-secondary" aria-hidden />
        <p className="min-w-0 flex-1 text-sm">
          {editing ? `Check the delivery address for Order ${number}` : notFound ? "No address in this message" : `Is this the delivery address for Order ${number}?`}
        </p>
        {editing ? null : notFound ? (
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
            Type it in
          </Button>
        ) : (
          <>
            <span className="text-2xs text-fg-secondary">1 AI credit</span>
            <Button size="sm" variant="secondary" loading={read.isPending} onClick={readAddress}>
              Read address
            </Button>
          </>
        )}
        <Button variant="ghost" size="icon-sm" aria-label="Dismiss address" className="-my-1 text-fg-secondary" onClick={onDone}>
          <X aria-hidden />
        </Button>
      </div>
      {editing ? (
        <form onSubmit={save} className="mt-2 flex flex-col gap-2">
          <AddressFields address={address} setAddress={setAddress} />
          <div className="flex justify-end">
            <Button type="submit" size="sm" loading={edit.isPending} disabled={Object.keys(filledAddress(address)).length === 0}>
              Save address
            </Button>
          </div>
        </form>
      ) : null}
    </section>
  );
}
