"use client";

import type { Route } from "next";
import Link from "next/link";

import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { useProducts } from "@/lib/api/queries";
import type { ProductNode } from "@/lib/automations/flow";
import { formatPrice, stockLabel } from "@/lib/catalogue/format";
import { useCurrentWorkspace } from "@/lib/workspace";

import { useFlowEnv } from "../FlowContext";
import { NativeSelect } from "../NativeSelect";

const INTRO_MAX = 300;

/**
 * A Product step (GR-31): pick a product from the catalogue, and optionally one of its variants
 * (size, colour…). When the step runs it sends the name, price, stock when recorded, the picture
 * and the link as they are then, with a line of your own above. The product list is read here, so
 * the flow editor needs nothing from its parent.
 */
export function ProductFields({ node }: { node: ProductNode }) {
  const env = useFlowEnv();
  const workspace = useCurrentWorkspace();
  const products = useProducts(env.wid, { q: "", active: true });
  const problems = env.problemsOf(node.id);
  const items = products.data?.items ?? [];
  const chosen = items.find((product) => product.id === node.product_id);
  const variant = chosen?.variants.find((item) => item.id === node.variant_id);
  const idFor = (part: string) => `flow-${node.id}-${part}`;
  const set = (change: Partial<ProductNode>) =>
    env.patch(node.id, (current) => (current.kind === "product" ? { ...current, ...change } : current));
  const productProblem = problems.product_id?.message;
  const variantProblem = problems.variant_id?.message;
  const introProblem = problems.intro?.message;

  return (
    <div className="space-y-3">
      <NativeSelect
        label="Product"
        value={node.product_id ?? ""}
        onChange={(value) => set({ product_id: value || null, variant_id: null })}
        invalid={Boolean(productProblem)}
        describedBy={productProblem ? idFor("product-error") : undefined}
      >
        <option value="">{products.isPending ? "Loading products" : "Choose a product"}</option>
        {items.map((product) => (
          <option key={product.id} value={product.id}>
            {product.name}
          </option>
        ))}
        {node.product_id && products.isSuccess && !chosen ? (
          <option value={node.product_id}>Deleted or switched off product</option>
        ) : null}
      </NativeSelect>
      {productProblem ? (
        <p id={idFor("product-error")} className="text-xs text-danger-fg">
          {productProblem}
        </p>
      ) : null}

      {chosen && chosen.variants.length > 0 ? (
        <>
          <NativeSelect
            label="Variant"
            value={node.variant_id ?? ""}
            onChange={(value) => set({ variant_id: value || null })}
            invalid={Boolean(variantProblem)}
            describedBy={variantProblem ? idFor("variant-error") : undefined}
          >
            <option value="">Any: list them</option>
            {chosen.variants.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </NativeSelect>
          {variantProblem ? (
            <p id={idFor("variant-error")} className="text-xs text-danger-fg">
              {variantProblem}
            </p>
          ) : null}
        </>
      ) : null}

      {chosen ? (
        <p className="rounded-lg border border-line bg-raised px-3 py-2 text-sm break-words">
          {variant
            ? `${chosen.name}, ${variant.title}: ${formatPrice(variant.price_minor, chosen.currency)}, ${stockLabel(variant.stock)}`
            : chosen.variants.length > 0
              ? `${chosen.name}: sends up to six variants with their prices`
              : `${chosen.name}: ${chosen.price_minor === null ? "No price" : formatPrice(chosen.price_minor, chosen.currency)}, ${stockLabel(chosen.stock)}`}
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
          placeholder="Here's the one you asked about:"
        />
        {introProblem ? <p className="text-xs text-danger-fg">{introProblem}</p> : null}
      </Field>
      <p className="text-xs text-fg-secondary">
        Price and stock are read when the step runs, so editing the product changes what people get. Stock is
        mentioned only when you track it.{" "}
        <Link href={`/w/${workspace.slug}/products` as Route} className="underline">
          Manage products
        </Link>
      </p>
    </div>
  );
}
