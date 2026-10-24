"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import { useProducts, useSendProductMessage, useWaCatalogue } from "@/lib/api/queries";
import type { Product, ProductMessageItem } from "@/lib/api/types";
import { formatPrice } from "@/lib/catalogue/format";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

const MAX_ITEMS = 30;
const MAX_SECTIONS = 10;

type Section = { key: string; title: string; picked: Set<string> };

let keyCounter = 0;
const nextSection = (title = ""): Section => ({ key: `s${(keyCounter += 1)}`, title, picked: new Set() });

/** One choosable row per variant, or per product without variants: the unit WhatsApp shows. */
function choices(products: Product[]): { id: string; label: string; item: ProductMessageItem }[] {
  return products.flatMap((product) =>
    product.variants.length > 0
      ? product.variants.map((variant) => ({
          id: variant.id,
          label: `${product.name} - ${variant.title} (${formatPrice(variant.price_minor, product.currency)})`,
          item: { product_id: product.id, variant_id: variant.id },
        }))
      : [
          {
            id: product.id,
            label: product.price_minor === null ? product.name : `${product.name} (${formatPrice(product.price_minor, product.currency)})`,
            item: { product_id: product.id, variant_id: null },
          },
        ],
  );
}

/**
 * Send a WhatsApp product message (one catalogue item) or product list (up to 30 items in up to 10
 * sections, under a header) in a conversation (GR-33). The customer sees name, price and picture
 * from the Meta catalogue, can add items to a cart and send it back, which makes an order. Only
 * items already in the catalogue can be sent; the dialog says when none are connected.
 */
export function SendProductDialog({
  conversationId,
  kind,
  open,
  onOpenChange,
}: {
  conversationId: string;
  kind: "product" | "product_list";
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { id: wid } = useCurrentWorkspace();
  const products = useProducts(wid, { q: "", active: true }, open);
  const catalogue = useWaCatalogue(wid, open);
  const send = useSendProductMessage(wid, conversationId);
  const options = choices(products.data?.items ?? []);
  const [body, setBody] = useState("");
  const [header, setHeader] = useState("");
  const [footer, setFooter] = useState("");
  const [single, setSingle] = useState("");
  const [sections, setSections] = useState<Section[]>(() => [nextSection("Products")]);
  const [problem, setProblem] = useState<string | null>(null);
  const list = kind === "product_list";
  const connected = catalogue.data?.connected && catalogue.data.status === "active";
  const total = sections.reduce((sum, section) => sum + section.picked.size, 0);

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) {
      setBody("");
      setHeader("");
      setFooter("");
      setSingle("");
      setSections([nextSection("Products")]);
      setProblem(null);
    }
  }

  function toggle(sectionKey: string, id: string, on: boolean) {
    setSections((current) =>
      current.map((section) => {
        if (section.key !== sectionKey) return section;
        const picked = new Set(section.picked);
        if (on) picked.add(id);
        else picked.delete(id);
        return { ...section, picked };
      }),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    const byId = new Map(options.map((option) => [option.id, option.item]));
    const onSuccess = () => {
      toast.success(list ? "Product list sent." : "Product sent.");
      close(false);
    };
    const onError = (error: unknown) => {
      if (isPlanLimitError(error)) return;
      if (error instanceof ApiError && [409, 422].includes(error.status)) {
        setProblem(error.errors[0]?.message ?? error.detail ?? null);
      } else toastError(error);
    };
    if (!list) {
      const item = byId.get(single);
      if (!item) return setProblem("Choose a product.");
      send.mutate({ kind: "product", body: body.trim(), footer: footer.trim() || null, item }, { onSuccess, onError });
      return;
    }
    if (!header.trim()) return setProblem("Add a header for the list.");
    const filled = sections.filter((section) => section.picked.size > 0);
    if (filled.length === 0) return setProblem("Choose at least one product.");
    if (filled.some((section) => !section.title.trim())) return setProblem("Give every section a title.");
    send.mutate(
      {
        kind: "product_list",
        body: body.trim(),
        header: header.trim(),
        footer: footer.trim() || null,
        sections: filled.map((section) => ({
          title: section.title.trim(),
          items: [...section.picked].flatMap((id) => (byId.get(id) ? [byId.get(id) as ProductMessageItem] : [])),
        })),
      },
      { onSuccess, onError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent size="lg" className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{list ? "Send product list" : "Send product"}</DialogTitle>
          <DialogDescription>
            {list
              ? "Show up to 30 products from your WhatsApp catalogue, in sections."
              : "Show one product from your WhatsApp catalogue, with its picture and price."}
          </DialogDescription>
        </DialogHeader>

        {catalogue.data && !connected ? (
          <Alert tone="warning">
            Connect a WhatsApp catalogue on the Products page first. Only products already in it can be sent.
          </Alert>
        ) : null}

        <form className="space-y-4" onSubmit={submit}>
          {list ? (
            <Field id="send-product-header">
              <FieldLabel>Header</FieldLabel>
              <Input maxLength={60} value={header} onChange={(event) => setHeader(event.target.value)} />
            </Field>
          ) : null}
          <Field id="send-product-body">
            <FieldLabel>Message</FieldLabel>
            <Textarea rows={2} maxLength={1024} value={body} onChange={(event) => setBody(event.target.value)} />
          </Field>

          {list ? (
            <div className="space-y-3">
              {sections.map((section, index) => (
                <fieldset key={section.key} className="space-y-2 rounded-lg border border-line p-3">
                  <legend className="px-1 text-sm font-medium">Section {index + 1}</legend>
                  <div className="flex items-end gap-2">
                    <label className="flex-1 text-sm">
                      <span className="sr-only">Section {index + 1} title</span>
                      <Input
                        maxLength={24}
                        placeholder="Section title"
                        value={section.title}
                        onChange={(event) =>
                          setSections((current) =>
                            current.map((item) => (item.key === section.key ? { ...item, title: event.target.value } : item)),
                          )
                        }
                      />
                    </label>
                    {sections.length > 1 ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove section ${index + 1}`}
                        onClick={() => setSections((current) => current.filter((item) => item.key !== section.key))}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    ) : null}
                  </div>
                  <ul className="max-h-40 space-y-1 overflow-y-auto" aria-label={`Products for section ${index + 1}`}>
                    {options.map((option) => (
                      <li key={option.id}>
                        <label className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={section.picked.has(option.id)}
                            disabled={!section.picked.has(option.id) && total >= MAX_ITEMS}
                            onCheckedChange={(value) => toggle(section.key, option.id, value === true)}
                          />
                          {option.label}
                        </label>
                      </li>
                    ))}
                  </ul>
                </fieldset>
              ))}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={sections.length >= MAX_SECTIONS}
                  onClick={() => setSections((current) => [...current, nextSection()])}
                >
                  <Plus aria-hidden /> Add section
                </Button>
                <span className="text-xs text-fg-secondary">
                  {total} of {MAX_ITEMS} products
                </span>
              </div>
            </div>
          ) : (
            <label className="block text-sm">
              <span className="font-medium">Product</span>
              <select
                value={single}
                onChange={(event) => setSingle(event.target.value)}
                className="mt-1 h-9 w-full rounded-lg border border-line-strong bg-field px-2 text-sm"
              >
                <option value="">Choose a product</option>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          <Field id="send-product-footer">
            <FieldLabel>Footer (optional)</FieldLabel>
            <Input maxLength={60} value={footer} onChange={(event) => setFooter(event.target.value)} />
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
            <Button type="submit" loading={send.isPending} disabled={!connected || !body.trim()}>
              Send
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
