"use client";

import type { Route } from "next";
import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useProducts } from "@/lib/api/queries";
import type { PaymentNode } from "@/lib/automations/flow";
import { formatPrice } from "@/lib/catalogue/format";
import { useCurrentWorkspace } from "@/lib/workspace";

import { useFlowEnv } from "../FlowContext";
import { NativeSelect } from "../NativeSelect";

const INTRO_MAX = 300;
const MAX_ITEMS = 10;

/**
 * A Request payment step (GR-32): make an order and send the payment message. Either the products
 * chosen here, ordered at the catalogue's prices when the step runs, or the conversation's latest
 * unpaid order (a member's draft, or the customer's WhatsApp cart). The message carries a Razorpay
 * link or a UPI request, whichever is chosen and set up under Payments. Part of Pro.
 */
export function PaymentFields({ node }: { node: PaymentNode }) {
  const env = useFlowEnv();
  const workspace = useCurrentWorkspace();
  const products = useProducts(env.wid, { q: "", active: true });
  const problems = env.problemsOf(node.id);
  const list = products.data?.items ?? [];
  const idFor = (part: string) => `flow-${node.id}-${part}`;
  const set = (change: Partial<PaymentNode>) =>
    env.patch(node.id, (current) => (current.kind === "payment" ? { ...current, ...change } : current));
  const setItem = (index: number, change: Partial<PaymentNode["items"][number]>) =>
    set({ items: node.items.map((item, i) => (i === index ? { ...item, ...change } : item)) });
  const itemsProblem = problems.items?.message;
  const methodProblem = problems.method?.message;
  const introProblem = problems.intro?.message;

  return (
    <div className="space-y-3">
      <NativeSelect label="Ask for" value={node.source} onChange={(value) => set({ source: value === "draft" ? "draft" : "items" })}>
        <option value="items">The products I choose</option>
        <option value="draft">The latest unpaid order in the chat</option>
      </NativeSelect>

      {node.source === "items" ? (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Products</legend>
          {node.items.map((item, index) => {
            const chosen = list.find((product) => product.id === item.product_id);
            const variantProblem = problems[`items.${index}.variant_id`]?.message;
            const productProblem = problems[`items.${index}.product_id`]?.message;
            return (
              <div key={`${item.product_id}-${index}`} className="space-y-1.5" data-testid="payment-item">
                <div className="flex flex-wrap items-end gap-2">
                  <NativeSelect
                    className="min-w-40 flex-1"
                    label={`Product ${index + 1}`}
                    value={item.product_id}
                    onChange={(value) => setItem(index, { product_id: value, variant_id: null })}
                    invalid={Boolean(productProblem)}
                  >
                    <option value="">{products.isPending ? "Loading products" : "Choose a product"}</option>
                    {list.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                    {item.product_id && products.isSuccess && !chosen ? (
                      <option value={item.product_id}>Deleted or switched off product</option>
                    ) : null}
                  </NativeSelect>
                  {chosen && chosen.variants.length > 0 ? (
                    <NativeSelect
                      className="min-w-32 flex-1"
                      label={`Variant ${index + 1}`}
                      value={item.variant_id ?? ""}
                      onChange={(value) => setItem(index, { variant_id: value || null })}
                      invalid={Boolean(variantProblem)}
                    >
                      <option value="">Choose a variant</option>
                      {chosen.variants.map((variant) => (
                        <option key={variant.id} value={variant.id}>
                          {variant.title} - {formatPrice(variant.price_minor, chosen.currency)}
                        </option>
                      ))}
                    </NativeSelect>
                  ) : null}
                  <label className="w-20 text-sm">
                    <span className="sr-only">Quantity {index + 1}</span>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      max={99}
                      value={item.quantity}
                      onChange={(event) =>
                        setItem(index, { quantity: Math.max(1, Math.min(99, Number.parseInt(event.target.value, 10) || 1)) })
                      }
                    />
                  </label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove product ${index + 1}`}
                    onClick={() => set({ items: node.items.filter((_, i) => i !== index) })}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </div>
                {productProblem ? <p className="text-xs text-danger-fg">{productProblem}</p> : null}
                {variantProblem ? <p className="text-xs text-danger-fg">{variantProblem}</p> : null}
              </div>
            );
          })}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={node.items.length >= MAX_ITEMS}
            onClick={() => set({ items: [...node.items, { product_id: "", variant_id: null, quantity: 1 }] })}
          >
            <Plus aria-hidden /> Add product
          </Button>
          {itemsProblem ? <p className="text-xs text-danger-fg">{itemsProblem}</p> : null}
        </fieldset>
      ) : (
        <p className="rounded-lg border border-line bg-raised px-3 py-2 text-sm">
          Uses the newest order in this chat that is not paid yet. If there is none, the step fails and the run log says
          so.
        </p>
      )}

      <NativeSelect
        label="Send"
        value={node.method}
        onChange={(value) => set({ method: value === "upi" ? "upi" : "razorpay" })}
        invalid={Boolean(methodProblem)}
        describedBy={methodProblem ? idFor("method-error") : undefined}
      >
        <option value="razorpay">A Razorpay payment link</option>
        <option value="upi">A UPI request (rupees only)</option>
      </NativeSelect>
      {methodProblem ? (
        <p id={idFor("method-error")} className="text-xs text-danger-fg">
          {methodProblem}
        </p>
      ) : null}

      <Field id={idFor("intro")}>
        <FieldLabel>Line above it (optional)</FieldLabel>
        <Textarea
          id={idFor("intro")}
          value={node.intro}
          maxLength={INTRO_MAX}
          rows={2}
          onChange={(event) => set({ intro: event.target.value })}
          aria-invalid={introProblem ? true : undefined}
          placeholder="Here's your order:"
        />
        {introProblem ? <p className="text-xs text-danger-fg">{introProblem}</p> : null}
      </Field>
      <p className="text-xs text-fg-secondary">
        The order is made when the step runs, at the prices in your catalogue then. Payments go to your own Razorpay or
        UPI account.{" "}
        <Link href={`/w/${workspace.slug}/orders` as Route} className="underline">
          Payment settings
        </Link>
      </p>
    </div>
  );
}
