"use client";

import { ExternalLink, Receipt, RotateCw } from "lucide-react";

import { SettingsCard } from "@/components/settings/SettingsCard";
import { EmptyState } from "@/components/states/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBillingPayments } from "@/lib/api/queries";
import type { Payment } from "@/lib/api/types";
import { billingDate } from "@/lib/billing/plan";
import { errorMessage, formatPrice } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

const STATUS: Record<Payment["status"], { label: string; tone: string }> = {
  succeeded: { label: "Paid", tone: "bg-success/15 text-success" },
  failed: { label: "Failed", tone: "bg-danger/15 text-danger-fg" },
  refunded: { label: "Refunded", tone: "bg-white/10 text-fg-secondary" },
  pending: { label: "Pending", tone: "bg-warning/15 text-warning" },
};

const TH = "px-5 py-2.5 text-left text-[11px] font-semibold tracking-[0.08em] text-fg-secondary uppercase md:px-6";

/**
 * C-066 payment history for owners and admins: each Dodo payment's date, amount and currency,
 * status (with Dodo's reason when it failed) and Dodo's invoice. Newest first; older pages on
 * demand. Nothing here is computed: rows come from Dodo's webhooks through GET …/billing/payments.
 */
export function PaymentHistory() {
  const workspace = useCurrentWorkspace();
  const payments = useBillingPayments(workspace.id);
  const items = payments.data?.pages.flatMap((page) => page.items) ?? [];

  let content;
  if (payments.isPending) {
    content = (
      <div className="space-y-3" aria-busy="true" aria-label="Loading payments">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-4 w-full bg-raised motion-reduce:animate-none" />
        ))}
      </div>
    );
  } else if (payments.isError) {
    content = (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
        <p className="flex-1 text-danger-fg">{errorMessage(payments.error)}</p>
        <Button variant="secondary" className="min-h-10" onClick={() => void payments.refetch()}>
          <RotateCw aria-hidden /> Try again
        </Button>
      </div>
    );
  } else if (items.length === 0) {
    content = (
      <EmptyState
        className="py-6"
        title="No payments yet"
        body="Charges show here from the first one. A trial isn't charged until it ends."
      />
    );
  } else {
    content = (
      <>
        <div className="-mx-5 overflow-x-auto md:-mx-6">
          <table className="w-full min-w-[520px] text-sm">
            <caption className="sr-only">Payments, newest first</caption>
            <thead className="border-y border-line-subtle">
              <tr>
                <th scope="col" className={TH}>
                  Date
                </th>
                <th scope="col" className={TH}>
                  Amount
                </th>
                <th scope="col" className={TH}>
                  Status
                </th>
                <th scope="col" className={cn(TH, "text-right")}>
                  Invoice
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-subtle">
              {items.map((payment) => {
                const date = billingDate(payment.occurred_at, workspace.timezone);
                const status = STATUS[payment.status];
                return (
                  <tr key={payment.id}>
                    <td className="px-5 py-3 whitespace-nowrap md:px-6">
                      <time dateTime={payment.occurred_at}>{date}</time>
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap tabular-nums md:px-6">
                      {formatPrice(payment)} <span className="text-xs text-fg-secondary">{payment.currency}</span>
                    </td>
                    <td className="px-5 py-3 md:px-6">
                      <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", status.tone)}>
                        {status.label}
                      </span>
                      {payment.status === "failed" && payment.failure_reason ? (
                        <span className="mt-1 block text-xs text-fg-secondary">{payment.failure_reason}</span>
                      ) : null}
                    </td>
                    <td className="px-5 py-3 text-right md:px-6">
                      {payment.invoice_url ? (
                        <a
                          href={payment.invoice_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Invoice for ${date} (opens in a new tab)`}
                          className="inline-flex min-h-10 items-center gap-1 rounded-md text-brand-fg underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-brand md:min-h-0"
                        >
                          Invoice <ExternalLink className="size-3.5" aria-hidden />
                        </a>
                      ) : (
                        <span className="text-fg-secondary">
                          <span aria-hidden>—</span>
                          <span className="sr-only">No invoice</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {payments.hasNextPage ? (
          <div className="flex justify-center pt-4">
            <Button
              variant="secondary"
              className="min-h-10"
              disabled={payments.isFetchingNextPage}
              onClick={() => void payments.fetchNextPage()}
            >
              {payments.isFetchingNextPage ? "Loading…" : "Show older payments"}
            </Button>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <SettingsCard
      id="payments"
      icon={<Receipt />}
      title="Payment history"
      description="Every charge Dodo Payments made for this workspace, newest first."
    >
      {content}
    </SettingsCard>
  );
}
