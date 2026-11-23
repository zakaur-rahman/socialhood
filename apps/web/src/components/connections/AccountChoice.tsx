import { Layers } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { SocialAccount } from "@/lib/api/types";
import { accountName } from "@/lib/inbox/format";

/** An account in an account filter (inbox, comments): its 24 px picture or initial, then its name. */
export function AccountChoice({ account }: { account: SocialAccount }) {
  const name = accountName(account);
  return (
    <span className="flex min-w-0 items-center gap-2">
      <Avatar size="sm" aria-hidden>
        {account.profile_picture_url ? <AvatarImage src={account.profile_picture_url} alt="" /> : null}
        <AvatarFallback className="bg-raised text-fg">{name.replace("@", "").slice(0, 1).toUpperCase()}</AvatarFallback>
      </Avatar>
      <span className="min-w-0 truncate">{name}</span>
    </span>
  );
}

/** "All accounts", with a stack icon the size of an account's picture, so the closed filter shows it too. */
export function AllAccountsChoice() {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-raised">
        <Layers className="size-3.5" />
      </span>
      <span className="min-w-0 truncate">All accounts</span>
    </span>
  );
}
