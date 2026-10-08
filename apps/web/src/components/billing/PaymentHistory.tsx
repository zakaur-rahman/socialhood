"use client";

import { ExternalLink, Receipt, RotateCw } from "lucide-react";

import { SettingsCard } from "@/components/settings/SettingsCard";
import { EmptyState } from "@/components/states/EmptyState";
import { Button } from "@/components/ui/button";
import { CardBleed } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBillingPayments } from "@/lib/api/queries";
import type { Payment } from "@/lib/api/types";
import { billingDate } from "@/lib/billing/plan";
import { errorMessage, formatPrice } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

const STATUS: Record<Payment["status"], { label: string; tone: string }> = {
  succeeded: { label: "Paid", tone: "bg-success-soft text-success" },
  failed: { label: "Failed", tone: "bg-danger-soft text-danger-fg" },
  // Neutral sits on `hover`: fg-secondary is 4.45:1 on white 10% (UI-ISS-007).
  refunded: { label: "Refunded", tone: "bg-hover text-fg-secondary" },
  pending: { label: "Pending", tone: "bg-warning-soft text-warning" },
};

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
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </div>
    );
  } else if (payments.isError) {
    content = (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
        <p className="flex-1 text-danger-fg">{errorMessage(payments.error)}</p>
        <Button variant="secondary" size="xl" onClick={() => void payments.refetch()}>
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
        <CardBleed className="border-t border-line-subtle">
          <Table className="min-w-130" scrollLabel="Payments">
            <TableCaption className="sr-only">Payments, newest first</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Invoice</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((payment) => {
                const date = billingDate(payment.occurred_at, workspace.timezone);
                const status = STATUS[payment.status];
                return (
                  <TableRow key={payment.id}>
                    <TableCell className="whitespace-nowrap">
                      <time dateTime={payment.occurred_at}>{date}</time>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatPrice(payment)} <span className="text-xs text-fg-secondary">{payment.currency}</span>
                    </TableCell>
                    <TableCell>
                      <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", status.tone)}>
                        {status.label}
                      </span>
                      {payment.status === "failed" && payment.failure_reason ? (
                        <span className="mt-1 block text-xs text-fg-secondary">{payment.failure_reason}</span>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right">
                      {payment.invoice_url ? (
                        <a
                          href={payment.invoice_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Invoice for ${date} (opens in a new tab)`}
                          className="inline-flex items-center gap-1 rounded-md text-brand-fg underline-offset-4 hover:underline pointer-coarse:min-h-10"
                        >
                          Invoice <ExternalLink className="size-3.5" aria-hidden />
                        </a>
                      ) : (
                        <span className="text-fg-secondary">
                          <span aria-hidden>—</span>
                          <span className="sr-only">No invoice</span>
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardBleed>
        {payments.hasNextPage ? (
          <div className="flex justify-center pt-4">
            <Button
              variant="secondary"
              size="xl"
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
    // --card-padding is the settings card's own padding (20 px, 24 px from md), so the table bleeds
    // to its edges and its edge cells line up with the title; Card sets it once SettingsCard moves
    // onto Card (UI-037).
    <SettingsCard
      id="payments"
      className="[--card-padding:--spacing(5)] md:[--card-padding:--spacing(6)]"
      icon={<Receipt />}
      title="Payment history"
      description="Every charge Dodo Payments made for this workspace, newest first."
    >
      {content}
    </SettingsCard>
  );
}
