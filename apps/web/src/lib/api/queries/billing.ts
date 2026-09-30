"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { useApi } from "../provider";
import type { BillingState, CheckoutSession, PaymentList, Plan, PlanList, PortalSession, UsageMeter } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** TR-BIL-04: plan, entitlements and usage. usage.updated refreshes it (FR-AI-05, C-049). */
export function useBilling(
  wid: string,
  enabled = true,
  options: Pick<UseQueryOptions<BillingState>, "refetchInterval"> = {},
) {
  const api = useApi();
  return useQuery<BillingState>({
    queryKey: keys.billing(wid),
    enabled,
    staleTime: 5 * 60_000,
    refetchInterval: options.refetchInterval,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/billing", { params: { path: { wid } } })),
  });
}

/** The public plan list (C-049): Free, Pro and Max with entitlements and Dodo prices. */
export function useBillingPlans(enabled = true) {
  const api = useApi();
  return useQuery<PlanList>({
    queryKey: keys.billingPlans,
    enabled,
    staleTime: 60 * 60_000, // the API caches Dodo's prices for an hour too
    queryFn: () => unwrap(api.GET("/v1/billing/plans")),
  });
}

const PAYMENTS_PAGE = 20;

/** C-066 payment history (owners and admins): Dodo payments, newest first, a page at a time. */
export function useBillingPayments(wid: string, enabled = true) {
  const api = useApi();
  return useInfiniteQuery<
    PaymentList,
    Error,
    InfiniteData<PaymentList, string | null>,
    ReturnType<typeof keys.billingPayments>,
    string | null
  >({
    queryKey: keys.billingPayments(wid),
    enabled,
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/billing/payments", {
          params: { path: { wid }, query: { cursor: pageParam ?? undefined, limit: PAYMENTS_PAGE } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/**
 * F-15 Checkout: Dodo's hosted checkout URL (and whether it starts the trial). 409 when a paid
 * plan exists, 422 for Max until R2 (C-049). The plan changes only when the webhook arrives.
 */
export function useCheckout(wid: string) {
  const api = useApi();
  return useMutation<CheckoutSession, Error, "pro" | "max">({
    mutationFn: (plan) =>
      unwrap(api.POST("/v1/w/{wid}/billing/checkout", { params: { path: { wid } }, body: { plan } })),
  });
}

/** FR-BIL-04: a Dodo customer portal session (payment method, invoices). 409 without a customer. */
export function usePortal(wid: string) {
  const api = useApi();
  return useMutation<PortalSession, Error, void>({
    mutationFn: () => unwrap(api.POST("/v1/w/{wid}/billing/portal", { params: { path: { wid } } })),
  });
}

function useBillingAction(wid: string, path: "/v1/w/{wid}/billing/cancel" | "/v1/w/{wid}/billing/resume") {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<BillingState, Error, void>({
    mutationFn: () => unwrap(api.POST(path, { params: { path: { wid } } })),
    onSuccess: (state) => queryClient.setQueryData(keys.billing(wid), state),
  });
}

/** FR-BIL-04: cancel at the end of the period; the answer has cancel_at_period_end. */
export function useCancelPlan(wid: string) {
  return useBillingAction(wid, "/v1/w/{wid}/billing/cancel");
}

/** Undo a cancellation before the period ends. */
export function useResumePlan(wid: string) {
  return useBillingAction(wid, "/v1/w/{wid}/billing/resume");
}

/**
 * Whether the plan allows Auto (FR-SUG-01: Auto needs a paid plan). The billing state's
 * ai_modes entitlement decides; until it loads, the plan name does.
 */
export function autoAllowed(billing: BillingState | undefined, plan: Plan): boolean {
  const modes = billing?.entitlements.find((item) => item.key === "ai_modes")?.value;
  if (Array.isArray(modes)) return modes.includes("auto");
  return plan !== "free";
}

export function usageMeter(billing: BillingState | undefined, metric: string): UsageMeter | null {
  return billing?.usage.find((meter) => meter.metric === metric) ?? null;
}

/** FR-AI-05: the AI credits meter when this period's credits are used up, else null. */
export function exhaustedAiCredits(billing: BillingState | undefined): UsageMeter | null {
  const meter = usageMeter(billing, "ai_credits");
  if (!meter || meter.limit === null || meter.limit === undefined) return null;
  return meter.used >= meter.limit ? meter : null;
}
