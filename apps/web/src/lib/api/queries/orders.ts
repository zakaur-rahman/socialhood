"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { INLINE_PLAN_LIMITS, useApi } from "../provider";
import type {
  Order,
  OrderCreate,
  OrderEditInput,
  OrderList,
  OrderNoticeInput,
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
  return useMutation<
    Order,
    Error,
    { orderId: string; method: OrderPaymentMethod; send: boolean; allowPartial?: boolean }
  >({
    mutationFn: ({ orderId, method, send, allowPartial }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/payment-request", {
          params: { path: { wid, order_id: orderId } },
          body: { method, send, allow_partial: allowPartial ?? false },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

/**
 * For UPI, which has no webhook: who, when and how much are kept on the order and in the audit
 * trail. `amountMinor` blank records everything that is left; less leaves the order partly paid.
 * `notice` also messages the customer; the answer's `notice` says whether it went.
 */
export function useMarkOrderPaid(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<
    Order,
    Error,
    { orderId: string; reference: string | null; amountMinor?: number | null; notice?: OrderNoticeInput | null }
  >({
    mutationFn: ({ orderId, reference, amountMinor, notice }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/mark-paid", {
          params: { path: { wid, order_id: orderId } },
          body: { reference, amount_minor: amountMinor ?? null, notice: notice ?? null },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

export function useCancelOrder(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, { orderId: string; notice?: OrderNoticeInput | null }>({
    mutationFn: ({ orderId, notice }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/cancel", {
          params: { path: { wid, order_id: orderId } },
          body: { notice: notice ?? null },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

/** Mark a paid order shipped, with a note for the order (a courier and tracking number). */
export function useFulfilOrder(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, { orderId: string; note: string | null; notice?: OrderNoticeInput | null }>({
    mutationFn: ({ orderId, note, notice }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/fulfil", {
          params: { path: { wid, order_id: orderId } },
          body: { note, notice: notice ?? null },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

/** Refund an order in full (`amountMinor` blank) or in part, with a reason. */
export function useRefundOrder(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<
    Order,
    Error,
    { orderId: string; amountMinor: number | null; reason: string; notice?: OrderNoticeInput | null }
  >({
    mutationFn: ({ orderId, amountMinor, reason, notice }) =>
      unwrap(
        api.POST("/v1/w/{wid}/orders/{order_id}/refunds", {
          params: { path: { wid, order_id: orderId } },
          body: { amount_minor: amountMinor, reason, notice: notice ?? null },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.orders(wid) }),
  });
}

/** Change a draft or waiting order; `payment` sends a new request straight after. */
export function useEditOrder(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Order, Error, { orderId: string; body: OrderEditInput }>({
    mutationFn: ({ orderId, body }) =>
      unwrap(api.PATCH("/v1/w/{wid}/orders/{order_id}", { params: { path: { wid, order_id: orderId } }, body })),
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
