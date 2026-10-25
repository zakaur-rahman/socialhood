import { AlertTriangle } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Alert, AlertAction } from "@/components/ui/alert";
import type { AccountAttention } from "@/lib/api/types";

function problem(account: AccountAttention): string {
  const fallback = {
    whatsapp: "Your WhatsApp number", facebook: "Your Facebook Page", instagram: "Your Instagram account",
    web: "Your website chat",
  };
  const name = account.username ? `@${account.username}` : fallback[account.platform];
  return account.status === "needs_reconnect"
    ? `${name} needs reconnecting to keep receiving messages`
    : `${name} has a connection error`;
}

/**
 * UX-SCR-01: account health, only when an account needs attention (needs reconnecting or in
 * error). An urgent Alert (a state to act on, UX-SH-04). Admins go to Connections to fix it;
 * agents are told who can.
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
    <Alert
      tone="warning"
      variant="outline"
      urgent
      aria-label="Account health"
      icon={<AlertTriangle />}
      action={
        canManage ? (
          <AlertAction asChild>
            <Link href={`/w/${slug}/settings/connections` as Route}>Open Connections</Link>
          </AlertAction>
        ) : undefined
      }
    >
      <ul className="space-y-1">
        {accounts.map((account) => (
          <li key={account.id} data-testid="account-attention">
            {problem(account)}.{canManage ? null : <span className="text-fg-secondary"> Ask an admin to fix it.</span>}
          </li>
        ))}
      </ul>
    </Alert>
  );
}
