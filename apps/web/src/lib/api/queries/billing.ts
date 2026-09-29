"use client";

import { useQuery } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { BillingState, Plan, UsageMeter } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** TR-BIL-04: plan, entitlements and usage. usage.updated refreshes it (FR-AI-05). */
export function useBilling(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<BillingState>({
    queryKey: keys.billing(wid),
    enabled,
    staleTime: 5 * 60_000,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/billing", { params: { path: { wid } } })),
  });
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
