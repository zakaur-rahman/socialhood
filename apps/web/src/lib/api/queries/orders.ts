"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type {
  Order,
  OrderCreate,
  OrderList,
  OrderPaymentMethod,
  OrderStatus,
  PaymentSettings,
  RazorpayConnectInput,
  UpiSaveInput,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/**
 * Orders (GR-32), newest first. Reading is never refused, so the page shows what exists on every
 * plan; `limits` says whether the plan allows making orders and which payment methods are set up.
 */
export function useOrders(wid: string, status: OrderStatus | null, enabled = true) {
  const api = useApi();
  return useQuery<OrderList>({
    queryKey: keys.orderList(wid, status),
    enabled,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/orders", {
          params: { path: { wid }, query: { status: status ?? undefined, limit: 200 } },
        }),
      ),
  });
}

/** 402 on Free (the dialog shows the upgrade path inline); 404 for a conversation or product that isn't ours. */
export function useCreateOrder(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, OrderCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/orders", { params: { path: { wid } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
    meta: INLINE_PLAN_LIMITS,
  });
}

/** Make the payment link or UPI request and, when `send`, post it in the order's conversation. */
export function useRequestPayment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, { orderId: string; method: OrderPaymentMethod; send: boolean }>({
    mutationFn: ({ orderId, method, send }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/payment-request", {
          params: { path: { wid, order_id: orderId } },
          body: { method, send },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

/** For UPI, which has no webhook: who and when are kept on the order and in the audit trail. */
export function useMarkOrderPaid(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, { orderId: string; reference: string | null }>({
    mutationFn: ({ orderId, reference }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/mark-paid", {
          params: { path: { wid, order_id: orderId } },
          body: { reference },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

export function useCancelOrder(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, string>({
    mutationFn: (orderId) =>
      unwrap(api.POST("/v1/w/{wid}/orders/{order_id}/cancel", { params: { path: { wid, order_id: orderId } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

// ---- payment settings

export function usePaymentSettings(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<PaymentSettings>({
    queryKey: keys.payments(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/integrations/payments", { params: { path: { wid } } })),
  });
}

/** Checks the keys with Razorpay before saving them: 422 when Razorpay refuses them. */
export function useConnectRazorpay(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<PaymentSettings, Error, RazorpayConnectInput>({
    mutationFn: (body) =>
      unwrap(api.PUT("/v1/w/{wid}/integrations/payments/razorpay", { params: { path: { wid } }, body })),
    onSuccess: (settings) => {
      queryClient.setQueryData(keys.payments(wid), settings);
      return queryClient.invalidateQueries({ queryKey: keys.orders(wid) });
    },
    meta: INLINE_PLAN_LIMITS,
  });
}

export function useDisconnectRazorpay(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      expectOk(api.DELETE("/v1/w/{wid}/integrations/payments/razorpay", { params: { path: { wid } } })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.payments(wid) }),
        queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
      ]),
  });
}

export function useSaveUpi(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<PaymentSettings, Error, UpiSaveInput>({
    mutationFn: (body) =>
      unwrap(api.PUT("/v1/w/{wid}/integrations/payments/upi", { params: { path: { wid } }, body })),
    onSuccess: (settings) => {
      queryClient.setQueryData(keys.payments(wid), settings);
      return queryClient.invalidateQueries({ queryKey: keys.orders(wid) });
    },
    meta: INLINE_PLAN_LIMITS,
  });
}

export function useRemoveUpi(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () => expectOk(api.DELETE("/v1/w/{wid}/integrations/payments/upi", { params: { path: { wid } } })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.payments(wid) }),
        queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
      ]),
  });
}
