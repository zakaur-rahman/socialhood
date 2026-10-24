"use client";

import { useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { Alert, AlertAction } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import { useCreateOrder, useOrders, useProducts, useRequestPayment } from "@/lib/api/queries";
import type { Order, OrderPaymentMethod } from "@/lib/api/types";
import { toastError } from "@/lib/toast-error";
import { orderNumber, orderTotal } from "@/lib/orders/format";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AddressFields, blankLine, filledAddress, itemsOf, OrderLinesFields, type Draft } from "./OrderLinesFields";

/**
 * Create an order in a conversation (GR-32): choose products, variants and quantities from the
 * catalogue, add the delivery address, then ask for payment with a Razorpay link or a UPI request
 * and send it in the chat. The total shown while typing is an estimate; the server prices the order
 * from the catalogue when it is created and the order keeps those prices. Making orders is part of
 * Pro (PD-8): without it the dialog says so instead of leaving a dead button.
 */
export function CreateOrderDialog({
  conversationId,
  open,
  onOpenChange,
}: {
  conversationId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { id: wid, role } = useCurrentWorkspace();
  const upgrade = useUpgradeDialog();
  const products = useProducts(wid, { q: "", active: true }, open);
  const orders = useOrders(wid, null, open);
  const create = useCreateOrder(wid);
  const request = useRequestPayment(wid);
  const [lines, setLines] = useState<Draft[]>(() => [blankLine()]);
  const [address, setAddress] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [created, setCreated] = useState<Order | null>(null);

  const catalogue = useMemo(() => new Map((products.data?.items ?? []).map((p) => [p.id, p])), [products.data]);
  const entitled = products.data?.limits.entitled ?? true;
  const limits = orders.data?.limits;
  const canUpgrade = role === "owner" || role === "admin";

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) {
      setLines([blankLine()]);
      setAddress({});
      setNote("");
      setProblem(null);
      setCreated(null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    const built = itemsOf(lines, catalogue);
    if ("problem" in built) return setProblem(built.problem);
    const filled = filledAddress(address);
    create.mutate(
      {
        conversation_id: conversationId,
        items: built.items,
        address: Object.keys(filled).length > 0 ? filled : null,
        note: note.trim() || null,
      },
      {
        onSuccess: (order) => {
          setCreated(order);
          toast.success(`Order ${orderNumber(order)} created.`);
        },
        onError: (error) => {
          if (isPlanLimitError(error)) return; // the upgrade dialog says it
          if (error instanceof ApiError && error.errors.length > 0) setProblem(error.errors[0]?.message ?? null);
          else toastError(error);
        },
      },
    );
  }

  function pay(method: OrderPaymentMethod) {
    if (!created) return;
    request.mutate(
      { orderId: created.id, method, send: true },
      {
        onSuccess: () => {
          toast.success(method === "razorpay" ? "Payment link sent." : "UPI request sent.");
          close(false);
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent size="lg" className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{created ? `Order ${orderNumber(created)} created` : "Create order"}</DialogTitle>
          <DialogDescription>
            {created
              ? `${orderTotal(created)} for ${created.items.length} ${created.items.length === 1 ? "item" : "items"}. Ask for payment in this chat.`
              : "Choose what they are buying. Prices come from your catalogue."}
          </DialogDescription>
        </DialogHeader>

        {created ? (
          <div className="space-y-3">
            {limits && !limits.razorpay_ready && !limits.upi_ready ? (
              <Alert tone="warning">
                Payments aren&rsquo;t set up. An owner or admin can add Razorpay or a UPI address on the Orders page.
              </Alert>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button disabled={!limits?.razorpay_ready} loading={request.isPending} onClick={() => pay("razorpay")}>
                Send Razorpay link
              </Button>
              <Button
                variant="secondary"
                disabled={!limits?.upi_ready}
                loading={request.isPending}
                onClick={() => pay("upi")}
              >
                Send UPI request
              </Button>
              <Button variant="ghost" onClick={() => close(false)}>
                Not now
              </Button>
            </div>
            <p className="text-xs text-fg-secondary">
              A UPI request has no confirmation from the bank, so you mark the order paid yourself on the Orders page.
            </p>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={submit}>
            {!entitled ? (
              <Alert
                tone="brand"
                action={
                  canUpgrade ? (
                    <AlertAction type="button" onClick={() => upgrade.open(COMMERCE_UPGRADE)}>
                      See plans
                    </AlertAction>
                  ) : undefined
                }
              >
                Orders are part of Pro.
              </Alert>
            ) : null}

            <OrderLinesFields
              lines={lines}
              setLines={setLines}
              products={products.data?.items ?? []}
              catalogue={catalogue}
              empty={Boolean(products.data && products.data.items.length === 0)}
            />

            <AddressFields address={address} setAddress={setAddress} />

            <Field id="order-note">
              <FieldLabel>Note</FieldLabel>
              <Textarea rows={2} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
            </Field>

            {problem ? (
              <p role="alert" className="text-sm text-danger-fg">
                {problem}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => close(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={create.isPending}>
                Create order
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
