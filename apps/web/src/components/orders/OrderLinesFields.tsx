"use client";

import { Plus, Trash2 } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { Order, OrderAddressInput, OrderLineInput, Product } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";

/** One line being typed: strings, because they are what the inputs hold. */
export type Draft = { key: string; productId: string; variantId: string; quantity: string };

let keyCounter = 0;
export const blankLine = (): Draft => ({ key: `l${(keyCounter += 1)}`, productId: "", variantId: "", quantity: "1" });

/** The lines of a saved order as drafts, to edit them. */
export function draftsOf(order: Pick<Order, "items">): Draft[] {
  const found = order.items
    .filter((line) => line.product_id)
    .map((line) => ({
      key: `l${(keyCounter += 1)}`,
      productId: line.product_id ?? "",
      variantId: line.variant_id ?? "",
      quantity: String(line.quantity),
    }));
  return found.length > 0 ? found : [blankLine()];
}

export const ADDRESS_FIELDS: { key: keyof OrderAddressInput; label: string; max: number }[] = [
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

/** "₹1,598.00" for the lines, or null while a line is unfinished. */
export function estimateOf(lines: Draft[], catalogue: Map<string, Product>): string | null {
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
}

/** The request's lines, or the first problem in plain words. */
export function itemsOf(
  lines: Draft[],
  catalogue: Map<string, Product>,
): { items: OrderLineInput[] } | { problem: string } {
  const items: OrderLineInput[] = [];
  for (const line of lines) {
    const product = catalogue.get(line.productId);
    const quantity = Number.parseInt(line.quantity, 10);
    if (!product) return { problem: "Choose a product for every line." };
    if (product.variants.length > 0 && !line.variantId) return { problem: `Choose a variant of ${product.name}.` };
    if (!(quantity >= 1 && quantity <= 999)) return { problem: "Quantities are between 1 and 999." };
    items.push({ product_id: product.id, variant_id: line.variantId || null, quantity });
  }
  return { items };
}

/** The filled-in address fields only. */
export function filledAddress(address: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(address).filter(([, value]) => value.trim() !== ""));
}

/** The products, variants and quantities of an order, as the dialogs that make or change one show them. */
export function OrderLinesFields({
  lines,
  setLines,
  products,
  catalogue,
  empty,
}: {
  lines: Draft[];
  setLines: Dispatch<SetStateAction<Draft[]>>;
  products: Product[];
  catalogue: Map<string, Product>;
  empty: boolean;
}) {
  function patchLine(key: string, change: Partial<Draft>) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...change } : line)));
  }
  const estimate = estimateOf(lines, catalogue);
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">Items</legend>
      {empty ? <p className="text-sm text-fg-secondary">Add products to your catalogue first.</p> : null}
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
                {products.map((item) => (
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
      <Button type="button" variant="secondary" size="sm" onClick={() => setLines((current) => [...current, blankLine()])}>
        <Plus aria-hidden /> Add item
      </Button>
      {estimate ? <p className="text-sm text-fg-secondary">About {estimate} in total.</p> : null}
    </fieldset>
  );
}

/** The delivery address inputs. */
export function AddressFields({
  address,
  setAddress,
}: {
  address: Record<string, string>;
  setAddress: Dispatch<SetStateAction<Record<string, string>>>;
}) {
  return (
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
  );
}
