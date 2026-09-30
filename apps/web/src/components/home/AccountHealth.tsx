import { AlertTriangle, ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import type { AccountAttention } from "@/lib/api/types";

function problem(account: AccountAttention): string {
  const name = account.username ? `@${account.username}` : account.platform === "whatsapp" ? "Your WhatsApp number" : "Your Instagram account";
  return account.status === "needs_reconnect"
    ? `${name} needs reconnecting to keep receiving messages`
    : `${name} has a connection error`;
}

/**
 * UX-SCR-01: account health, only when an account needs attention (needs reconnecting or in
 * error). Admins go to Connections to fix it; agents are told who can.
 */
export function AccountHealth({
  accounts,
  slug,
  canManage,
}: {
  accounts: AccountAttention[];
  slug: string;
  canManage: boolean;
}) {
  if (accounts.length === 0) return null;
  return (
    <section aria-label="Account health" className="rounded-xl border border-warning/40 bg-panel p-4">
      <ul className="space-y-2">
        {accounts.map((account) => (
          <li key={account.id} data-testid="account-attention" className="flex items-start gap-3 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
            <span className="flex-1">
              {problem(account)}.{canManage ? null : <span className="text-fg-secondary"> Ask an admin to fix it.</span>}
            </span>
          </li>
        ))}
      </ul>
      {canManage ? (
        <Link
          href={`/w/${slug}/settings/connections` as Route}
          className="mt-3 inline-flex min-h-10 items-center gap-1 text-sm font-medium text-brand-fg hover:underline md:min-h-8"
        >
          Open Connections <ChevronRight className="size-4" aria-hidden />
        </Link>
      ) : null}
    </section>
  );
}
