"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { useUpgradeDialog } from "@/lib/api/provider";
import { useBilling } from "@/lib/api/queries";
import { canStartCheckout } from "@/lib/billing/plan";
import { PRO_PLAN_PARAM } from "@/lib/resolve";
import { useCurrentWorkspace } from "@/lib/workspace";

import { PLAN_UPGRADE } from "./upgrade-requests";

/**
 * UI-ISS-073: "Start free, then try Pro" on the pricing page carries `?plan=pro` through sign-up
 * (lib/resolve.ts) to Home. When the owner of a workspace without a paid plan lands with it, the
 * upgrade dialog opens once and offers the trial; the parameter is dropped either way, so a reload
 * or a shared link doesn't ask again. It renders nothing.
 */
export function ProTrialOffer() {
  const params = useSearchParams();
  const workspace = useCurrentWorkspace();
  const upgrade = useUpgradeDialog();
  const wanted = params?.get("plan") === PRO_PLAN_PARAM;
  const isOwner = workspace.role === "owner";
  const billing = useBilling(workspace.id, wanted && isOwner);
  const handled = useRef(false);

  useEffect(() => {
    if (!wanted || handled.current) return;
    if (isOwner && billing.isPending) return;
    handled.current = true;
    // C-149: nothing to offer while paid plans aren't on sale.
    if (isOwner && billing.data && canStartCheckout(billing.data)) upgrade.open(PLAN_UPGRADE);
    // Next syncs a native history call with useSearchParams, so the parameter goes without a navigation.
    window.history.replaceState(window.history.state, "", window.location.pathname);
  }, [wanted, isOwner, billing.isPending, billing.data, upgrade]);

  return null;
}
