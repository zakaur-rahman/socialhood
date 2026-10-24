"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type {
  CsvImportPreview,
  CsvImportResult,
  Product,
  ProductCreate,
  ProductList,
  ProductPatch,
  ShopifyStatus,
} from "../types";
import { keys, type ProductFilters } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** While a Shopify sync runs, the card and the list refresh this often. */
export const SHOPIFY_POLL_MS = 4_000;

/**
 * The catalogue (GR-31): products newest first, searched on the server, with the plan's limits.
 * Reading is never refused, so the page shows what exists on every plan. `enabled` lets a picker
 * wait until it opens.
 */
export function useProducts(wid: string, filters: ProductFilters, enabled = true) {
  const api = useApi();
  return useQuery<ProductList>({
    queryKey: keys.productList(wid, filters),
    enabled,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/products", {
          params: {
            path: { wid },
            query: { q: filters.q || undefined, active: filters.active ?? undefined, limit: 200 },
          },
        }),
      ),
  });
}

export function useProduct(wid: string, productId: string | null) {
  const api = useApi();
  return useQuery<Product>({
    queryKey: [...keys.products(wid), "one", productId] as const,
    enabled: Boolean(productId),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/products/{product_id}", { params: { path: { wid, product_id: productId as string } } })),
  });
}

/** 402 entitlement_required on Free; the form shows the upgrade path inline and keeps what was typed. */
export function useCreateProduct(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Product, Error, ProductCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/products", { params: { path: { wid } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.products(wid) }),
    meta: INLINE_PLAN_LIMITS,
  });
}

export function useUpdateProduct(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Product, Error, { id: string; patch: ProductPatch }>({
    mutationFn: ({ id, patch }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/products/{product_id}", { params: { path: { wid, product_id: id } }, body: patch }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.products(wid) }),
    meta: INLINE_PLAN_LIMITS,
  });
}

export function useDeleteProduct(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/products/{product_id}", { params: { path: { wid, product_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.products(wid) }),
  });
}

// ---- CSV import

/** What the file would do, line by line. Saves nothing. */
export function usePreviewProductImport(wid: string) {
  const api = useApi();
  return useMutation<CsvImportPreview, Error, string>({
    mutationFn: (csv) =>
      unwrap(api.POST("/v1/w/{wid}/products/import/preview", { params: { path: { wid } }, body: { csv } })),
    meta: INLINE_PLAN_LIMITS,
  });
}

export function useImportProducts(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<CsvImportResult, Error, string>({
    mutationFn: (csv) => unwrap(api.POST("/v1/w/{wid}/products/import", { params: { path: { wid } }, body: { csv } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.products(wid) }),
    meta: INLINE_PLAN_LIMITS,
  });
}

// ---- Shopify

export function useShopify(wid: string) {
  const api = useApi();
  return useQuery<ShopifyStatus>({
    queryKey: keys.shopify(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/integrations/shopify", { params: { path: { wid } } })),
    refetchInterval: (query) => (query.state.data?.syncing ? SHOPIFY_POLL_MS : false),
  });
}

/** Shopify's install address; the caller navigates there. 402 on Free, 503 until the app is set up. */
export function useStartShopifyConnect(wid: string) {
  const api = useApi();
  return useMutation<string, Error, string>({
    mutationFn: async (shop) =>
      (
        await unwrap(
          api.POST("/v1/w/{wid}/integrations/shopify/connect", { params: { path: { wid } }, body: { shop } }),
        )
      ).authorize_url,
    meta: INLINE_PLAN_LIMITS,
  });
}

/**
 * The OAuth callback sends the browser back with ?shopify=<nonce>; this finishes the connect as the
 * signed-in member. Only the member who started it can (403 otherwise), once and within 10 minutes.
 */
export function useCompleteShopifyConnect(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ShopifyStatus, Error, string>({
    mutationFn: (nonce) =>
      unwrap(api.POST("/v1/w/{wid}/integrations/shopify/complete", { params: { path: { wid } }, body: { nonce } })),
    onSuccess: (status) => queryClient.setQueryData(keys.shopify(wid), status),
  });
}

export function useSyncShopify(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ShopifyStatus, Error, void>({
    mutationFn: () => unwrap(api.POST("/v1/w/{wid}/integrations/shopify/sync", { params: { path: { wid } } })),
    onSuccess: (status) => queryClient.setQueryData(keys.shopify(wid), status),
  });
}

export function useDisconnectShopify(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, { keepProducts: boolean }>({
    mutationFn: ({ keepProducts }) =>
      expectOk(
        api.DELETE("/v1/w/{wid}/integrations/shopify", {
          params: { path: { wid }, query: { keep_products: keepProducts } },
        }),
      ),
    onSuccess: () => Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.shopify(wid) }),
      queryClient.invalidateQueries({ queryKey: keys.products(wid) }),
    ]),
  });
}
