"use client";

import { FileUp, Pencil, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { PageFrame } from "@/components/shell/PageFrame";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBleed } from "@/components/ui/card";
import { SearchInput } from "@/components/ui/search-input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useUpgradeDialog } from "@/lib/api/provider";
import { useDeleteProduct, useProducts } from "@/lib/api/queries";
import type { Product } from "@/lib/api/types";
import { priceLabel, productStock } from "@/lib/catalogue/format";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

import { ImportDialog } from "./ImportDialog";
import { ProductSheet, type ProductUploader } from "./ProductSheet";
import { ShopifyCard } from "./ShopifyCard";
import { WhatsAppCatalogueCard } from "./WhatsAppCatalogueCard";

const SOURCE_LABEL: Record<Product["source"], string> = {
  manual: "Added here",
  csv: "CSV import",
  shopify: "Shopify",
};

type Filter = "all" | "active" | "off";

/**
 * Products (GR-31, under Grow beside Knowledge): the catalogue the AI quotes prices, stock and links
 * from, and the "send product" flow step reads. Add products by hand, import a CSV file, or copy
 * them from Shopify. Reading is on every plan; adding, importing and syncing are part of Pro (PD-8),
 * and the page says so and opens the upgrade dialog instead of leaving a dead button. Owners and admins.
 */
export function ProductsPage({ upload }: { upload?: ProductUploader }) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const upgrade = useUpgradeDialog();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const products = useProducts(wid, { q: query.trim(), active: filter === "all" ? null : filter === "active" });
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const limits = products.data?.limits;
  const entitled = limits?.entitled ?? true;
  const canUpgrade = workspace.role === "owner" || workspace.role === "admin";
  const items = products.data?.items ?? [];

  // A plain action when the plan allows it; the upgrade dialog when it doesn't.
  const guarded = (action: () => void) => () => (entitled ? action() : upgrade.open(COMMERCE_UPGRADE));

  return (
    <PageFrame
      title="Products"
      actions={
        <>
          <Button variant="secondary" onClick={guarded(() => setImporting(true))}>
            <FileUp aria-hidden /> Import CSV
          </Button>
          <Button onClick={guarded(() => setEditing("new"))}>
            <Plus aria-hidden /> Add product
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {!entitled ? (
          <Alert tone="brand">
            The product catalogue is part of Pro. You can see what is here, but adding, importing and syncing products
            need Pro.{" "}
            {canUpgrade ? (
              <button type="button" className="underline underline-offset-4" onClick={() => upgrade.open(COMMERCE_UPGRADE)}>
                See plans
              </button>
            ) : null}
          </Alert>
        ) : null}

        <ShopifyCard wid={wid} />
        <WhatsAppCatalogueCard wid={wid} />

        <Card asChild padding="roomy">
          <section aria-labelledby="catalogue-title">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <h2 id="catalogue-title" className="text-base font-semibold">
                  Catalogue
                </h2>
                <p className="text-sm text-fg-secondary">
                  What the AI may quote: names, prices, stock and links, exactly as written here.
                  {products.data ? ` ${products.data.total} ${products.data.total === 1 ? "product" : "products"}.` : ""}
                </p>
              </div>
              <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                <SearchInput
                  label="Search products"
                  placeholder="Name, SKU or variant"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="w-full sm:w-64"
                />
                <label className="sr-only" htmlFor="product-filter">
                  Show
                </label>
                <select
                  id="product-filter"
                  value={filter}
                  onChange={(event) => setFilter(event.target.value as Filter)}
                  className="h-9 rounded-lg border border-line-strong bg-field px-2 text-sm"
                >
                  <option value="all">All products</option>
                  <option value="active">Offered to customers</option>
                  <option value="off">Switched off</option>
                </select>
              </div>
            </div>

            <CardBleed className="mt-5 border-t border-line">
              {products.isPending ? (
                <div className="space-y-3 p-(--card-padding)" role="status" aria-busy="true" aria-label="Loading products">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              ) : products.isError ? (
                <div className="p-(--card-padding)">
                  <ErrorState error={products.error} onRetry={() => void products.refetch()} />
                </div>
              ) : items.length === 0 ? (
                <Empty
                  searching={query.trim() !== "" || filter !== "all"}
                  entitled={entitled}
                  onAdd={guarded(() => setEditing("new"))}
                  onImport={guarded(() => setImporting(true))}
                />
              ) : (
                <ProductTable items={items} onEdit={(product) => setEditing(product)} wid={wid} />
              )}
            </CardBleed>
          </section>
        </Card>
      </div>

      <ProductSheet
        product={editing === "new" ? null : editing}
        open={editing !== null}
        onOpenChange={(open) => (open ? undefined : setEditing(null))}
        limits={limits}
        upload={upload}
      />
      <ImportDialog open={importing} onOpenChange={setImporting} limits={limits} />
    </PageFrame>
  );
}

function Empty({
  searching,
  entitled,
  onAdd,
  onImport,
}: {
  searching: boolean;
  entitled: boolean;
  onAdd: () => void;
  onImport: () => void;
}) {
  if (searching) {
    return (
      <div className="p-(--card-padding)">
        <EmptyState size="compact" title="No products match" body="Try another word, or show all products." />
      </div>
    );
  }
  return (
    <div className="p-(--card-padding)">
      <EmptyState
        icon={<ShoppingBag />}
        title="No products yet"
        body={
          entitled
            ? "Add what you sell, import a CSV file, or connect Shopify. The AI then answers price, stock and link questions from here."
            : "The product catalogue is part of Pro. Upgrade to add what you sell, and the AI can answer price, stock and link questions."
        }
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Button onClick={onAdd}>
              <Plus aria-hidden /> Add product
            </Button>
            <Button variant="secondary" onClick={onImport}>
              <FileUp aria-hidden /> Import CSV
            </Button>
          </div>
        }
      />
    </div>
  );
}

function ProductTable({ items, onEdit, wid }: { items: Product[]; onEdit: (product: Product) => void; wid: string }) {
  const remove = useDeleteProduct(wid);
  const [deleting, setDeleting] = useState<Product | null>(null);
  const returnFocus = useReturnFocus();
  return (
    <>
      <Table scrollLabel="Products">
        <TableCaption className="sr-only">Products, newest first</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead>Price</TableHead>
            <TableHead>Stock</TableHead>
            <TableHead>Source</TableHead>
            <TableHead className="w-24">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((product) => (
            <TableRow key={product.id} data-testid="product-row">
              <TableCell className="min-w-56">
                <div className="flex items-start gap-3">
                  {product.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- the product's own picture
                    <img src={product.image_url} alt="" loading="lazy" className="size-10 shrink-0 rounded-lg object-cover" />
                  ) : (
                    <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-lg bg-raised text-fg-secondary">
                      <ShoppingBag className="size-4" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="font-medium break-words">{product.name}</p>
                    <p className="text-xs text-fg-secondary">
                      {product.variants.length > 0
                        ? `${product.variants.length} ${product.variants.length === 1 ? "variant" : "variants"}`
                        : (product.sku ?? "No variants")}
                      {product.active ? "" : " · Switched off"}
                    </p>
                  </div>
                </div>
              </TableCell>
              <TableCell>{priceLabel(product)}</TableCell>
              <TableCell>{productStock(product)}</TableCell>
              <TableCell>
                <Badge tone={product.source === "shopify" ? "brand" : "neutral"}>{SOURCE_LABEL[product.source]}</Badge>
              </TableCell>
              <TableCell>
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" size="icon-sm" aria-label={`Edit ${product.name}`} onClick={() => onEdit(product)}>
                    <Pencil aria-hidden />
                  </Button>
                  <Button
                    variant="destructive-ghost"
                    size="icon-sm"
                    aria-label={`Delete ${product.name}`}
                    onClick={() => setDeleting(product)}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <AlertDialog open={deleting !== null} onOpenChange={(open) => (open ? undefined : setDeleting(null))}>
        <AlertDialogContent {...returnFocus}>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting?.source === "shopify"
                ? "It comes back at the next Shopify sync unless you remove it in Shopify too. "
                : ""}
              A flow that sends this product will stop at that step.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!deleting) return;
                remove.mutate(deleting.id, {
                  onSuccess: () => toast.success("Product deleted"),
                  onError: (error) => toastError(error),
                });
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
