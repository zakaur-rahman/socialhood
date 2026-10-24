"use client";

import { AlertTriangle, ImagePlus, Plus, Trash2, X } from "lucide-react";
import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { toast } from "sonner";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { COMMERCE_UPGRADE } from "@/components/billing/upgrade-requests";
import { Alert, AlertAction } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, isPlanLimitError } from "@/lib/api/errors";
import { upgradeRequestFrom, useApi, useUpgradeDialog, type UpgradeRequest } from "@/lib/api/provider";
import { useCreateProduct, useUpdateProduct } from "@/lib/api/queries";
import type { CatalogueLimits, MediaAsset, Product, ProductCreate, ProductVariantInput } from "@/lib/api/types";
import { linkProblem, priceProblem } from "@/lib/catalogue/format";
import { errorMessage } from "@/lib/copy";
import { uploadAsset, UploadError } from "@/lib/media/upload";
import { useCurrentWorkspace } from "@/lib/workspace";

/** Tests inject a fake; the app uploads through the API and Cloudinary as an image. */
export type ProductUploader = (file: File) => Promise<MediaAsset>;

const MAX_VARIANTS = 100;

type VariantDraft = {
  key: string;
  /** The variant's id when it exists: it keeps the id, and so every flow step that names it. */
  id: string | null;
  title: string;
  price: string;
  stock: string;
  sku: string;
  /** Not edited here (a CSV or Shopify import sets them); sent back as they were. */
  options: Record<string, string>;
};

export type ProductFormValues = {
  name: string;
  description: string;
  sku: string;
  currency: string;
  price: string;
  stock: string;
  url: string;
  active: boolean;
  imageAssetId: string | null;
  imageUrl: string | null;
  variants: VariantDraft[];
};

type Errors = Record<string, string>;

let keyCounter = 0;
const nextKey = () => `v${(keyCounter += 1)}`;

function initial(product: Product | null, defaultCurrency: string): ProductFormValues {
  if (!product) {
    return {
      name: "",
      description: "",
      sku: "",
      currency: defaultCurrency,
      price: "",
      stock: "",
      url: "",
      active: true,
      imageAssetId: null,
      imageUrl: null,
      variants: [],
    };
  }
  return {
    name: product.name,
    description: product.description ?? "",
    sku: product.sku ?? "",
    currency: product.currency,
    price: product.price ?? "",
    stock: product.stock === null ? "" : String(product.stock),
    url: product.url ?? "",
    active: product.active,
    imageAssetId: product.image_asset_id ?? null,
    imageUrl: product.image_url ?? null,
    variants: product.variants.map((variant) => ({
      key: nextKey(),
      id: variant.id,
      title: variant.title,
      price: variant.price,
      stock: variant.stock === null ? "" : String(variant.stock),
      sku: variant.sku ?? "",
      options: variant.options,
    })),
  };
}

function stockProblem(text: string): string | null {
  if (!text.trim()) return null;
  return /^\d{1,8}$/.test(text.trim()) ? null : "Enter a whole number, or leave it blank when you don't track stock.";
}

/** What is wrong with the form before it is sent, by the field the API would name. */
export function problems(values: ProductFormValues): Errors {
  const out: Errors = {};
  if (!values.name.trim()) out.name = "Enter the product's name.";
  if (!/^[A-Za-z]{3}$/.test(values.currency.trim())) out.currency = "Use a three-letter currency code, like INR or USD.";
  const link = linkProblem(values.url);
  if (link) out.url = link;
  if (values.variants.length === 0) {
    const price = priceProblem(values.price, values.currency);
    if (price) out.price = price;
    const stock = stockProblem(values.stock);
    if (stock) out.stock = stock;
  }
  const titles = new Set<string>();
  values.variants.forEach((variant, index) => {
    const key = `variants.${index}`;
    if (!variant.title.trim()) out[`${key}.title`] = "Name the variant, like M or Blue / M.";
    else if (titles.has(variant.title.trim().toLowerCase())) out[`${key}.title`] = "Two variants have the same name. Give each its own.";
    titles.add(variant.title.trim().toLowerCase());
    const price = priceProblem(variant.price, values.currency);
    if (price) out[`${key}.price`] = price;
    const stock = stockProblem(variant.stock);
    if (stock) out[`${key}.stock`] = stock;
  });
  return out;
}

function variantBody(variant: VariantDraft): ProductVariantInput {
  return {
    ...(variant.id ? { id: variant.id } : {}),
    title: variant.title.trim(),
    options: variant.options,
    sku: variant.sku.trim() || null,
    price: variant.price.trim(),
    stock: variant.stock.trim() ? Number(variant.stock.trim()) : null,
  };
}

/** The create body for the form's values. */
export function createBody(values: ProductFormValues): ProductCreate {
  return {
    name: values.name.trim(),
    description: values.description.trim() || null,
    sku: values.sku.trim() || null,
    currency: values.currency.trim().toUpperCase(),
    price: values.variants.length === 0 ? values.price.trim() : null,
    stock: values.variants.length === 0 && values.stock.trim() ? Number(values.stock.trim()) : null,
    url: values.url.trim() || null,
    image_asset_id: values.imageAssetId,
    active: values.active,
    variants: values.variants.map(variantBody),
  };
}

/**
 * Add or change a product (GR-31): name, price, stock, picture and link, and variants (size,
 * colour…) that each have their own price, stock and SKU. With variants the product's own price and
 * stock are not used. A blank stock means "not tracked", which is different from 0: the AI says it
 * doesn't know, and never calls it in stock. Owners and admins; the catalogue is part of Pro.
 */
export function ProductSheet({
  product,
  open,
  onOpenChange,
  limits,
  upload,
}: {
  /** null: a new product. */
  product: Product | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  limits: CatalogueLimits | undefined;
  upload?: ProductUploader;
}) {
  const returnFocus = useReturnFocus();
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" size="panel" className="gap-0 overflow-y-auto p-0" {...returnFocus}>
        <SheetHeader className="border-b border-line p-4 pr-12">
          <SheetTitle>{product ? "Edit product" : "Add a product"}</SheetTitle>
          <SheetDescription>
            The AI quotes these prices, stock levels and links to customers, exactly as you write them.
          </SheetDescription>
        </SheetHeader>
        {open ? (
          <ProductForm
            key={product?.id ?? "new"}
            product={product}
            limits={limits}
            upload={upload}
            onDone={() => onOpenChange(false)}
            onCancel={() => onOpenChange(false)}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function ProductForm({
  product,
  limits,
  upload,
  onDone,
  onCancel,
}: {
  product: Product | null;
  limits: CatalogueLimits | undefined;
  upload?: ProductUploader;
  onDone: () => void;
  onCancel: () => void;
}) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const api = useApi();
  const create = useCreateProduct(wid);
  const update = useUpdateProduct(wid);
  const upgrade = useUpgradeDialog();
  const [values, setValues] = useState<ProductFormValues>(() => initial(product, limits?.default_currency ?? "INR"));
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [overLimit, setOverLimit] = useState<UpgradeRequest | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const saving = create.isPending || update.isPending;
  const withVariants = values.variants.length > 0;
  const set = (change: Partial<ProductFormValues>) => setValues((current) => ({ ...current, ...change }));
  const setVariant = (key: string, change: Partial<VariantDraft>) =>
    setValues((current) => ({
      ...current,
      variants: current.variants.map((variant) => (variant.key === key ? { ...variant, ...change } : variant)),
    }));

  const fail = (error: unknown) => {
    if (isPlanLimitError(error)) {
      setOverLimit(upgradeRequestFrom(error));
      return;
    }
    if (error instanceof ApiError && error.errors.length > 0) {
      setErrors(Object.fromEntries(error.errors.map((field) => [field.field, field.message])));
      return;
    }
    setFormError(error instanceof UploadError ? error.message : errorMessage(error));
  };

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!chosen) return;
    setFormError(null);
    setUploading(true);
    try {
      const asset = upload ? await upload(chosen) : await uploadAsset(api, wid, chosen, { resourceType: "image" });
      set({ imageAssetId: asset.id, imageUrl: asset.secure_url ?? null });
    } catch (error) {
      setFormError(error instanceof UploadError ? error.message : errorMessage(error));
    } finally {
      setUploading(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setOverLimit(null);
    const found = problems(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const body = createBody(values);
    if (product) {
      update.mutate(
        { id: product.id, patch: { ...body, image_asset_id: values.imageAssetId } },
        {
          onSuccess: () => {
            toast.success("Product saved");
            onDone();
          },
          onError: fail,
        },
      );
      return;
    }
    create.mutate(body, {
      onSuccess: () => {
        toast.success("Product added");
        onDone();
      },
      onError: fail,
    });
  };

  const canUpgrade = workspace.role === "owner" || workspace.role === "admin";

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5 p-4" aria-label={product ? "Edit product" : "Add a product"}>
      <Field id="product-name" invalid={Boolean(errors.name)}>
        <FieldLabel>Name</FieldLabel>
        <Input maxLength={200} value={values.name} onChange={(event) => set({ name: event.target.value })} />
        <FieldError>{errors.name}</FieldError>
      </Field>
      <Field id="product-description">
        <FieldLabel>Description (optional)</FieldLabel>
        <Textarea
          rows={3}
          maxLength={2000}
          value={values.description}
          onChange={(event) => set({ description: event.target.value })}
        />
      </Field>
      <div className="grid grid-cols-[minmax(0,1fr)_6rem] gap-3">
        <Field id="product-url" invalid={Boolean(errors.url)}>
          <FieldLabel>Link (optional)</FieldLabel>
          <Input
            type="url"
            inputMode="url"
            placeholder="https://"
            maxLength={2000}
            value={values.url}
            onChange={(event) => set({ url: event.target.value })}
          />
          <FieldDescription>Where a customer can see or buy it.</FieldDescription>
          <FieldError>{errors.url}</FieldError>
        </Field>
        <Field id="product-currency" invalid={Boolean(errors.currency)}>
          <FieldLabel>Currency</FieldLabel>
          <Input
            maxLength={3}
            value={values.currency}
            onChange={(event) => set({ currency: event.target.value.toUpperCase() })}
          />
          <FieldError>{errors.currency}</FieldError>
        </Field>
      </div>

      {withVariants ? null : (
        <div className="grid grid-cols-2 gap-3">
          <Field id="product-price" invalid={Boolean(errors.price)}>
            <FieldLabel>Price</FieldLabel>
            <Input
              inputMode="decimal"
              placeholder="799"
              value={values.price}
              onChange={(event) => set({ price: event.target.value })}
            />
            <FieldError>{errors.price}</FieldError>
          </Field>
          <Field id="product-stock" invalid={Boolean(errors.stock)}>
            <FieldLabel>In stock (optional)</FieldLabel>
            <Input
              inputMode="numeric"
              placeholder="Not tracked"
              value={values.stock}
              onChange={(event) => set({ stock: event.target.value })}
            />
            <FieldError>{errors.stock}</FieldError>
          </Field>
        </div>
      )}

      <section aria-label="Variants" className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-sm font-medium">Variants</p>
            <p className="text-xs text-fg-secondary">
              For sizes, colours and the like. Each has its own price, stock and SKU, and the AI answers per variant.
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={values.variants.length >= MAX_VARIANTS}
            onClick={() =>
              set({
                variants: [
                  ...values.variants,
                  { key: nextKey(), id: null, title: "", price: values.price, stock: "", sku: "", options: {} },
                ],
              })
            }
          >
            <Plus aria-hidden /> Add variant
          </Button>
        </div>
        {values.variants.map((variant, index) => {
          const at = `variants.${index}`;
          return (
            <fieldset key={variant.key} className="space-y-3 rounded-lg border border-line p-3">
              <legend className="px-1 text-xs text-fg-secondary">Variant {index + 1}</legend>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field id={`variant-${variant.key}-title`} invalid={Boolean(errors[`${at}.title`])}>
                  <FieldLabel>Variant name</FieldLabel>
                  <Input
                    maxLength={120}
                    placeholder="Blue / M"
                    value={variant.title}
                    onChange={(event) => setVariant(variant.key, { title: event.target.value })}
                  />
                  <FieldError>{errors[`${at}.title`]}</FieldError>
                </Field>
                <Field id={`variant-${variant.key}-sku`} invalid={Boolean(errors[`${at}.sku`])}>
                  <FieldLabel>SKU (optional)</FieldLabel>
                  <Input
                    maxLength={80}
                    value={variant.sku}
                    onChange={(event) => setVariant(variant.key, { sku: event.target.value })}
                  />
                  <FieldError>{errors[`${at}.sku`]}</FieldError>
                </Field>
                <Field id={`variant-${variant.key}-price`} invalid={Boolean(errors[`${at}.price`])}>
                  <FieldLabel>Price</FieldLabel>
                  <Input
                    inputMode="decimal"
                    value={variant.price}
                    onChange={(event) => setVariant(variant.key, { price: event.target.value })}
                  />
                  <FieldError>{errors[`${at}.price`]}</FieldError>
                </Field>
                <Field id={`variant-${variant.key}-stock`} invalid={Boolean(errors[`${at}.stock`])}>
                  <FieldLabel>In stock (optional)</FieldLabel>
                  <Input
                    inputMode="numeric"
                    placeholder="Not tracked"
                    value={variant.stock}
                    onChange={(event) => setVariant(variant.key, { stock: event.target.value })}
                  />
                  <FieldError>{errors[`${at}.stock`]}</FieldError>
                </Field>
              </div>
              <Button
                type="button"
                variant="destructive-ghost"
                size="sm"
                onClick={() => set({ variants: values.variants.filter((item) => item.key !== variant.key) })}
              >
                <Trash2 aria-hidden /> Remove variant
              </Button>
            </fieldset>
          );
        })}
      </section>

      <Field id="product-picture">
        <FieldLabel>Picture (optional)</FieldLabel>
        <div className="flex items-center gap-3">
          {values.imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- a user's own picture from the media library or the store
            <img src={values.imageUrl} alt="" className="size-14 rounded-lg border border-line object-cover" />
          ) : null}
          <Button type="button" variant="secondary" size="sm" loading={uploading} onClick={() => fileRef.current?.click()}>
            <ImagePlus aria-hidden /> {values.imageUrl ? "Change picture" : "Add a picture"}
          </Button>
          {values.imageAssetId ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => set({ imageAssetId: null, imageUrl: null })}>
              <X aria-hidden /> Remove
            </Button>
          ) : null}
          <input
            ref={fileRef}
            type="file"
            className="sr-only"
            accept="image/jpeg,image/png,image/webp"
            onChange={onFile}
            data-testid="product-picture-input"
          />
        </div>
        <FieldDescription>Sent with the product in a chat. JPG, PNG or WebP.</FieldDescription>
      </Field>

      <Field id="product-sku">
        <FieldLabel>SKU (optional)</FieldLabel>
        <Input maxLength={80} value={values.sku} onChange={(event) => set({ sku: event.target.value })} disabled={withVariants} />
        <FieldDescription>
          {withVariants ? "Give each variant its own SKU." : "A code of your own. It lets a CSV import find this product again."}
        </FieldDescription>
        <FieldError>{errors.sku}</FieldError>
      </Field>

      <Field id="product-active" orientation="horizontal">
        <Checkbox checked={values.active} onCheckedChange={(value) => set({ active: value === true })} />
        <FieldLabel className="font-normal">Offer this product to customers</FieldLabel>
      </Field>

      {overLimit ? (
        <Alert
          tone="warning"
          urgent
          icon={<AlertTriangle />}
          action={
            canUpgrade ? (
              <AlertAction type="button" onClick={() => upgrade.open(overLimit.entitlement ? overLimit : COMMERCE_UPGRADE)}>
                Upgrade
              </AlertAction>
            ) : undefined
          }
        >
          {overLimit.code === "quota_exceeded"
            ? `${overLimit.detail ?? "Your plan's product limit is reached."} Remove a product or upgrade for more.`
            : "The product catalogue is part of Pro."}
        </Alert>
      ) : null}
      {formError ? (
        <p role="alert" className="text-sm text-danger-fg">
          {formError}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={saving} disabled={uploading}>
          {product ? "Save" : "Add product"}
        </Button>
      </div>
    </form>
  );
}
