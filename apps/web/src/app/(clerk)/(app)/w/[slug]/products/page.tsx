import type { Metadata } from "next";

import { ProductsPage } from "@/components/products/ProductsPage";

export const metadata: Metadata = { title: "Products" };

/** GR-31: the product catalogue. */
export default function ProductsRoute() {
  return <ProductsPage />;
}
