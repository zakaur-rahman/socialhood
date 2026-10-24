"use client";

import { useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { NativeSelect } from "@/components/automations/flow/NativeSelect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import { useEditOrder, useProducts } from "@/lib/api/queries";
import type { Order, OrderPaymentMethod } from "@/lib/api/types";
import { orderNumber } from "@/lib/orders/format";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AddressFields, draftsOf, filledAddress, itemsOf, OrderLinesFields, type Draft } from "./OrderLinesFields";

/**
 * Change an order until someone has paid it (GR-32): the lines are priced again from the catalogue
 * when it is saved, and the address and note are replaced. A new total makes the payment link
 * useless, so it is cancelled and the order goes back to a draft; ticking "Send a new payment
 * request" makes and sends the new one in the same step.
 */
export function EditOrderDialog({
  order,
  open,
  onOpenChange,
}: {
  order: Order;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { id: wid } = useCurrentWorkspace();
  const products = useProducts(wid, { q: "", active: true }, open);
  const edit = useEditOrder(wid);
  const [lines, setLines] = useState<Draft[]>(() => draftsOf(order));
  const [address, setAddress] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(order.address ?? {}).filter(([, value]) => typeof value === "string" && value)),
  );
  const [note, setNote] = useState(order.note ?? "");
  const [resend, setResend] = useState(order.status === "awaiting_payment");
  const [method, setMethod] = useState<OrderPaymentMethod>(order.payment_method ?? "razorpay");
  const [problem, setProblem] = useState<string | null>(null);
  const catalogue = useMemo(() => new Map((products.data?.items ?? []).map((p) => [p.id, p])), [products.data]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    const built = itemsOf(lines, catalogue);
    if ("problem" in built) return setProblem(built.problem);
    edit.mutate(
      {
        orderId: order.id,
        body: {
          items: built.items,
          address: filledAddress(address),
          note: note.trim(),
          payment: resend && order.conversation_id ? { method, send: true } : null,
        },
      },
      {
        onSuccess: (changed) => {
          toast.success(
            changed.status === "draft" && order.status === "awaiting_payment"
              ? `Order ${orderNumber(order)} changed. Its old payment link no longer works.`
              : `Order ${orderNumber(order)} changed.`,
          );
          onOpenChange(false);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.errors.length > 0) setProblem(error.errors[0]?.message ?? null);
          else toastError(error);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg" className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Change order {orderNumber(order)}</DialogTitle>
          <DialogDescription>
            Prices are read from your catalogue again when you save. You can change an order until someone pays it.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <OrderLinesFields
            lines={lines}
            setLines={setLines}
            products={products.data?.items ?? []}
            catalogue={catalogue}
            empty={Boolean(products.data && products.data.items.length === 0)}
          />
          <AddressFields address={address} setAddress={setAddress} />
          <Field id="order-edit-note">
            <FieldLabel>Note</FieldLabel>
            <Textarea rows={2} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
          </Field>
          {order.status === "awaiting_payment" && order.conversation_id ? (
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={resend} onCheckedChange={(on) => setResend(on === true)} />
                Send a new payment request when I save
              </label>
              {resend ? (
                <NativeSelect label="Send" value={method} onChange={(value) => setMethod(value === "upi" ? "upi" : "razorpay")}>
                  <option value="razorpay">A Razorpay payment link</option>
                  <option value="upi">A UPI request</option>
                </NativeSelect>
              ) : null}
            </div>
          ) : null}
          {problem ? (
            <p role="alert" className="text-sm text-danger-fg">
              {problem}
            </p>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={edit.isPending}>
              Save changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
