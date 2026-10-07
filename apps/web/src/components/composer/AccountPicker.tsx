"use client";

import { Check } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useMemo } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import type { SocialAccount } from "@/lib/api/types";
import { initial } from "@/lib/inbox/format";
import { cannotPublishReason, handleOf } from "@/lib/publishing/rules";
import { instagramAccountColors, type AccountColor } from "@/lib/schedule/format";
import { IDENTITY_FILL } from "@/lib/ui/identity";
import { cn } from "@/lib/utils";

import { Section } from "./Section";

export function accountChipId(accountId: string): string {
  return `composer-account-${accountId}`;
}

/**
 * The account's picture, or its initial on its identity's gradient: the identity Schedule gives the
 * same account (`instagramAccountColors`), not a hash of its id, so an account looks the same on
 * both screens. An account without an identity (disconnected, or the preview's placeholder) gets
 * the neutral fill. The initial is decorative: the handle is always beside it.
 */
export function AccountPicture({
  account,
  identity,
  size = 32,
}: {
  account: SocialAccount | null;
  identity?: AccountColor;
  size?: 24 | 32;
}) {
  const name = account?.username ?? account?.display_name ?? "?";
  return (
    <Avatar className={size === 32 ? "size-8" : "size-6"} data-testid="account-picture">
      {account?.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
      <AvatarFallback
        aria-hidden
        className={cn("font-semibold", identity?.gradient ? [IDENTITY_FILL, identity.gradient] : "text-fg", size === 32 ? "text-sm" : "text-2xs")}
      >
        {initial(name)}
      </AvatarFallback>
    </Avatar>
  );
}

/**
 * UX-SCR-13 Accounts: a toggle chip per Instagram account, in the order chosen (the first one's
 * name and picture lead the preview). An account that can't publish is disabled with the reason;
 * one already on the post stays clickable so it can be taken off.
 */
export function AccountPicker({
  accounts,
  loading,
  selected,
  onToggle,
  slug,
}: {
  /** The workspace's Instagram accounts. */
  accounts: SocialAccount[];
  loading: boolean;
  /** Selected account ids, in order. */
  selected: string[];
  onToggle: (accountId: string) => void;
  slug: string;
}) {
  const connectHref = `/w/${slug}/settings/connections` as Route;
  const identities = useMemo(() => instagramAccountColors(accounts), [accounts]);
  return (
    <Section id="composer-accounts" title="Accounts" tabIndex={-1}>
      {loading ? (
        <div className="flex gap-2" aria-busy="true" aria-label="Loading accounts">
          <Skeleton className="h-10 w-36 rounded-full" />
          <Skeleton className="h-10 w-36 rounded-full" />
        </div>
      ) : accounts.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          Connect an Instagram business or creator account to publish posts.{" "}
          <Link href={connectHref} className="text-brand-fg underline-offset-4 hover:underline">
            Connect Instagram
          </Link>
        </p>
      ) : (
        <ul className="flex flex-wrap gap-2" aria-label="Instagram accounts">
          {accounts.map((account) => {
            const isSelected = selected.includes(account.id);
            const reason = cannotPublishReason(account);
            const reasonId = `${accountChipId(account.id)}-reason`;
            return (
              <li key={account.id} className="flex flex-col gap-1">
                <button
                  type="button"
                  id={accountChipId(account.id)}
                  aria-pressed={isSelected}
                  aria-describedby={reason ? reasonId : undefined}
                  disabled={Boolean(reason) && !isSelected}
                  onClick={() => onToggle(account.id)}
                  className={cn(
                    "inline-flex min-h-10 items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-sm font-medium transition-[color,background-color,border-color] duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-50",
                    isSelected ? "border-brand bg-brand-soft text-fg" : "border-line text-fg-secondary hover:bg-hover hover:text-fg",
                    isSelected && reason && "border-danger",
                  )}
                >
                  <AccountPicture account={account} identity={identities.get(account.id)} />
                  {handleOf(account)}
                  {isSelected ? <Check className="size-4 text-brand-fg" aria-hidden /> : null}
                </button>
                {reason ? (
                  <span id={reasonId} className="px-2 text-xs text-fg-secondary">
                    {reason}
                    {" · "}
                    <Link href={connectHref} className="text-brand-fg underline-offset-4 hover:underline">
                      Reconnect
                    </Link>
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}
