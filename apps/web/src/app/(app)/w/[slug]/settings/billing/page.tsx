import type { Metadata } from "next";
import { Suspense } from "react";

import { BillingPage } from "@/components/billing/BillingPage";
import { PageSkeleton } from "@/components/states/PageSkeleton";

export const metadata: Metadata = { title: "Billing" };

/** UX-SCR-07 Billing (T8.4, F-15); Dodo returns here with ?checkout=return. */
export default function BillingRoute() {
  return (
    <Suspense fallback={<PageSkeleton rows={3} />}>
      <BillingPage />
    </Suspense>
  );
}
