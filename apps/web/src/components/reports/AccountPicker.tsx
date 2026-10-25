import { Layers } from "lucide-react";

import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Platform, ReportAccount } from "@/lib/api/types";
import { PLATFORM_LABEL } from "@/lib/inbox/format";

const ALL = "all";

/**
 * Which account the report is for: every account together (the default) or one connected account,
 * each with its platform's mark. The choice is the address's `?account=`, so a link reproduces it.
 */
export function AccountPicker({
  accounts,
  value,
  onPick,
}: {
  accounts: ReportAccount[];
  /** The picked account's id, or null for all of them. */
  value: string | null;
  onPick: (account: string | null) => void;
}) {
  // An account asked for by address stays selectable even if the list doesn't have it (yet).
  const selected = value ?? ALL;
  return (
    <Select value={selected} onValueChange={(next) => onPick(next === ALL ? null : next)}>
      <SelectTrigger aria-label="Account" className="w-52 max-w-full" data-testid="account-picker">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL} icon={<Layers className="size-4" aria-hidden />}>
          All accounts
        </SelectItem>
        {accounts.map((account) => (
          <SelectItem
            key={account.id}
            value={account.id}
            icon={<PlatformGlyph platform={account.platform as Platform} className="size-4" />}
            description={PLATFORM_LABEL[account.platform as Platform] ?? account.platform}
          >
            {account.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
