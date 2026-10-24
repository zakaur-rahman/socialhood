/**
 * The catalogue's presentation rules (GR-31). Pure functions, tested directly.
 *
 * Money is integer minor units with an ISO 4217 code (the API's rule); it is shown with Intl, so
 * the symbol, grouping and decimals follow the currency (and the person's locale). Stock is null
 * when it was never recorded, which is not the same as 0: "Not tracked" against "Out of stock".
 */
import type { Product, ProductVariant } from "@/lib/api/types";

/** The columns a CSV import reads, in the API's order (services/catalogue/csv_import.COLUMNS). */
export const CSV_COLUMNS = [
  "name",
  "description",
  "sku",
  "variant",
  "option1_name",
  "option1_value",
  "option2_name",
  "option2_value",
  "option3_name",
  "option3_value",
  "price",
  "currency",
  "stock",
  "url",
  "image_url",
  "active",
] as const;

/** A starter file: a product with sizes, and a plain one. Downloaded from the import dialog. */
export const CSV_TEMPLATE = [
  CSV_COLUMNS.join(","),
  "Cotton kurta,Soft cotton. Straight cut.,KUR-BL-S,Blue / S,Colour,Blue,799,INR,12,https://example.com/kurta,yes",
  "Cotton kurta,,KUR-BL-M,Blue / M,Colour,Blue,799,INR,5,,",
  "Silk scarf,Hand dyed,SCARF-1,,,,499,INR,,https://example.com/scarf,yes",
].join("\n");

/** The API's ceiling on a pasted or uploaded file (schemas/catalogue.CSV_MAX_CHARS). */
export const CSV_MAX_CHARS = 900_000;

function fractionDigits(currency: string): number {
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
  } catch {
    return 2;
  }
}

/** 79900 INR as "₹799.00" (or whatever the locale makes of it). */
export function formatPrice(minor: number, currency: string, locale?: string): string {
  const digits = fractionDigits(currency);
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(minor / 10 ** digits);
  } catch {
    return `${currency} ${(minor / 10 ** digits).toFixed(digits)}`;
  }
}

/** The price a customer would see in a list: one price, "from … to …" across variants, or none. */
export function priceLabel(product: Pick<Product, "currency" | "price_minor" | "variants">, locale?: string): string {
  const prices = product.variants.map((variant) => variant.price_minor);
  if (prices.length === 0) {
    return product.price_minor === null ? "No price" : formatPrice(product.price_minor, product.currency, locale);
  }
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  return low === high
    ? formatPrice(low, product.currency, locale)
    : `${formatPrice(low, product.currency, locale)} to ${formatPrice(high, product.currency, locale)}`;
}

/** "12 in stock", "Out of stock", or "Not tracked" (never recorded: the AI says it doesn't know). */
export function stockLabel(stock: number | null): string {
  if (stock === null) return "Not tracked";
  return stock <= 0 ? "Out of stock" : `${stock.toLocaleString("en")} in stock`;
}

/** The list's stock cell: the product's, or its variants' total when they all record stock. */
export function productStock(product: Pick<Product, "stock" | "variants">): string {
  if (product.variants.length === 0) return stockLabel(product.stock);
  if (product.variants.some((variant) => variant.stock === null)) {
    const known = product.variants.filter((variant) => variant.stock !== null);
    if (known.length === 0) return "Not tracked";
    return `${known.length} of ${product.variants.length} variants tracked`;
  }
  const total = product.variants.reduce((sum, variant) => sum + (variant.stock ?? 0), 0);
  return stockLabel(total);
}

/** "Blue / M" for a variant the way a flow step or a list names it. */
export function variantName(variant: Pick<ProductVariant, "title">): string {
  return variant.title;
}

/** Digits of a price field as the API reads them: "799", "799.5", "1,299.00". null when it isn't one. */
export function parsePrice(text: string, currency: string): string | null {
  const cleaned = text.trim().replace(/[, ]/g, "");
  if (!/^\d{1,13}(\.\d{1,3})?$/.test(cleaned)) return null;
  const places = fractionDigits(currency);
  const fraction = cleaned.split(".")[1] ?? "";
  if (fraction.length > places) return null;
  return cleaned;
}

/** Why a price field is wrong, in plain words, or null when it is fine. */
export function priceProblem(text: string, currency: string): string | null {
  if (!text.trim()) return "Enter a price.";
  if (parsePrice(text, currency)) return null;
  const places = fractionDigits(currency);
  return places === 0
    ? `${currency} prices have no decimal places.`
    : `Enter the price as a number with up to ${places} decimal places, like 799 or 799.50.`;
}

/** An https address, or why not. Blank is fine (the link is optional). */
export function linkProblem(text: string): string | null {
  if (!text.trim()) return null;
  try {
    return new URL(text.trim()).protocol === "https:" ? null : "Enter a link that starts with https://.";
  } catch {
    return "Enter a link that starts with https://.";
  }
}

/** The file's text, or why it can't be imported. */
export async function readCsvFile(file: File): Promise<{ text: string } | { error: string }> {
  if (file.size > CSV_MAX_CHARS) return { error: "That file is too large. Split it into smaller files." };
  const text = await file.text();
  if (text.length > CSV_MAX_CHARS) return { error: "That file is too large. Split it into smaller files." };
  return { text };
}
