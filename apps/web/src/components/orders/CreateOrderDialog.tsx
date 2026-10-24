"use client";

import { Plus, Trash2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { Alert, AlertAction } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import { useUpgradeDialog } from "@/lib/api/provider";
import { useCreateOrder, useOrders, useProducts, useRequestPayment } from "@/lib/api/queries";
import type { Order, OrderAddressInput, OrderPaymentMethod, Product } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";
import { toastError } from "@/lib/toast-error";
import { orderNumber, orderTotal } from "@/lib/orders/format";
import { useCurrentWorkspace } from "@/lib/workspace";

type Draft = { key: string; productId: string; variantId: string; quantity: string };

let keyCounter = 0;
const blank = (): Draft => ({ key: `l${(keyCounter += 1)}`, productId: "", variantId: "", quantity: "1" });

const ADDRESS_FIELDS: { key: keyof OrderAddressInput; label: string; max: number }[] = [
  { key: "name", label: "Name", max: 120 },
  { key: "phone", label: "Phone", max: 30 },
  { key: "line1", label: "Address line 1", max: 200 },
  { key: "line2", label: "Address line 2", max: 200 },
  { key: "city", label: "City", max: 100 },
  { key: "state", label: "State", max: 100 },
  { key: "pincode", label: "Pincode", max: 12 },
];

/** The price one line would have: shown as an estimate, since the server prices the order itself. */
function unitMinor(product: Product | undefined, variantId: string): number | null {
  if (!product) return null;
  if (product.variants.length > 0) return product.variants.find((v) => v.id === variantId)?.price_minor ?? null;
  return product.price_minor ?? null;
}

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
  const [lines, setLines] = useState<Draft[]>(() => [blank()]);
  const [address, setAddress] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [created, setCreated] = useState<Order | null>(null);

  const catalogue = useMemo(() => new Map((products.data?.items ?? []).map((p) => [p.id, p])), [products.data]);
  const entitled = products.data?.limits.entitled ?? true;
  const limits = orders.data?.limits;
  const canUpgrade = role === "owner" || role === "admin";

  const estimate = useMemo(() => {
    let total = 0;
    let currency: string | null = null;
    for (const line of lines) {
      const product = catalogue.get(line.productId);
      const unit = unitMinor(product, line.variantId);
      const quantity = Number.parseInt(line.quantity, 10);
      if (!product || unit === null || !(quantity >= 1)) return null;
      currency = product.currency;
      total += unit * quantity;
    }
    return currency ? formatPrice(total, currency) : null;
  }, [lines, catalogue]);

  function patchLine(key: string, change: Partial<Draft>) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...change } : line)));
  }

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) {
      setLines([blank()]);
      setAddress({});
      setNote("");
      setProblem(null);
      setCreated(null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    const items = [];
    for (const line of lines) {
      const product = catalogue.get(line.productId);
      const quantity = Number.parseInt(line.quantity, 10);
      if (!product) return setProblem("Choose a product for every line.");
      if (product.variants.length > 0 && !line.variantId) return setProblem(`Choose a variant of ${product.name}.`);
      if (!(quantity >= 1 && quantity <= 999)) return setProblem("Quantities are between 1 and 999.");
      items.push({ product_id: product.id, variant_id: line.variantId || null, quantity });
    }
    const filled = Object.fromEntries(Object.entries(address).filter(([, value]) => value.trim() !== ""));
    create.mutate(
      {
        conversation_id: conversationId,
        items,
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

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Items</legend>
              {products.data && products.data.items.length === 0 ? (
                <p className="text-sm text-fg-secondary">Add products to your catalogue first.</p>
              ) : null}
              {lines.map((line, index) => {
                const product = catalogue.get(line.productId);
                return (
                  <div key={line.key} className="flex flex-wrap items-end gap-2" data-testid="order-line">
                    <label className="min-w-40 flex-1 text-sm">
                      <span className="sr-only">Product {index + 1}</span>
                      <select
                        value={line.productId}
                        onChange={(event) => patchLine(line.key, { productId: event.target.value, variantId: "" })}
                        className="h-9 w-full rounded-lg border border-line-strong bg-field px-2 text-sm"
                      >
                        <option value="">Choose a product</option>
                        {(products.data?.items ?? []).map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    {product && product.variants.length > 0 ? (
                      <label className="min-w-32 flex-1 text-sm">
                        <span className="sr-only">Variant {index + 1}</span>
                        <select
                          value={line.variantId}
                          onChange={(event) => patchLine(line.key, { variantId: event.target.value })}
                          className="h-9 w-full rounded-lg border border-line-strong bg-field px-2 text-sm"
                        >
                          <option value="">Choose a variant</option>
                          {product.variants.map((variant) => (
                            <option key={variant.id} value={variant.id}>
                              {variant.title} - {formatPrice(variant.price_minor, product.currency)}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <label className="w-20 text-sm">
                      <span className="sr-only">Quantity {index + 1}</span>
                      <Input
                        type="number"
                        inputMode="numeric"
                        min={1}
                        max={999}
                        value={line.quantity}
                        onChange={(event) => patchLine(line.key, { quantity: event.target.value })}
                      />
                    </label>
                    {lines.length > 1 ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove item ${index + 1}`}
                        onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    ) : null}
                  </div>
                );
              })}
              <Button type="button" variant="secondary" size="sm" onClick={() => setLines((current) => [...current, blank()])}>
                <Plus aria-hidden /> Add item
              </Button>
              {estimate ? <p className="text-sm text-fg-secondary">About {estimate} in total.</p> : null}
            </fieldset>

            <fieldset className="grid gap-2 sm:grid-cols-2">
              <legend className="mb-1 text-sm font-medium">Delivery address</legend>
              {ADDRESS_FIELDS.map((item) => (
                <Field key={item.key} id={`order-${item.key}`}>
                  <FieldLabel>{item.label}</FieldLabel>
                  <Input
                    maxLength={item.max}
                    value={address[item.key] ?? ""}
                    onChange={(event) => setAddress((current) => ({ ...current, [item.key]: event.target.value }))}
                  />
                </Field>
              ))}
            </fieldset>

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
