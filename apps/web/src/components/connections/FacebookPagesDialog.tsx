"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useConnectFacebookPages, useFacebookPages } from "@/lib/api/queries";
import type { FacebookPageOption } from "@/lib/api/types";
import { facebookConnected, facebookListError } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";

/** The Pages worth pre-checking: connectable, and not connected already. */
export function defaultPicks(pages: FacebookPageOption[]): Set<string> {
  const open = pages.filter((page) => page.can_connect && !page.connected);
  return new Set(open.length === 1 ? [open[0].id] : []);
}

/**
 * GR-29: after Facebook Login, the Pages the person manages, to pick from. A Page they can't answer
 * messages for is listed with the reason and can't be picked; one already connected can be picked
 * again to reconnect it. The nonce (from the OAuth callback's ?facebook=) is spent when the Pages
 * connect, so a refusal (the plan's limit, a Page in use) leaves the list open to choose again.
 */
export function FacebookPagesDialog({
  wid,
  nonce,
  onClose,
}: {
  wid: string;
  /** The nonce to list Pages with; null: closed. */
  nonce: string | null;
  onClose: () => void;
}) {
  const list = useFacebookPages(wid);
  const connect = useConnectFacebookPages(wid);
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const { mutate: load } = list;

  useEffect(() => {
    if (nonce) load(nonce);
  }, [nonce, load]);

  const pages = list.data?.items ?? [];
  const chosen = picked ?? defaultPicks(pages);
  const toggle = (id: string, on: boolean) => {
    const next = new Set(chosen);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };

  const submit = () => {
    if (!nonce || chosen.size === 0) return;
    connect.mutate(
      { nonce, pageIds: pages.filter((page) => chosen.has(page.id)).map((page) => page.id) },
      {
        onSuccess: (accounts) => {
          toast.success(facebookConnected(accounts.map((account) => account.display_name ?? account.username ?? "Page")));
          onClose();
        },
        // Over accounts_per_platform (402): the upgrade dialog says so, and the list stays.
        onError: (error) => toastError(error),
      },
    );
  };

  return (
    <Dialog open={nonce !== null} onOpenChange={(open) => (open || connect.isPending ? undefined : onClose())}>
      <DialogContent data-testid="facebook-pages-dialog">
        <DialogHeader>
          <DialogTitle>Choose your Facebook Pages</DialogTitle>
          <DialogDescription>
            Amplychat reads and answers messages and comments for the Pages you pick. You can disconnect a Page later.
          </DialogDescription>
        </DialogHeader>
        {list.isPending || list.isIdle ? (
          <div role="status" aria-busy="true" aria-label="Loading your Pages" className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : list.isError ? (
          <p role="alert" className="text-sm text-danger-fg">
            {facebookListError(list.error)}
          </p>
        ) : (
          <ul className="max-h-80 space-y-2 overflow-y-auto" aria-label="Your Facebook Pages">
            {pages.map((page) => (
              <PageRow key={page.id} page={page} checked={chosen.has(page.id)} onChange={(on) => toggle(page.id, on)} />
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button variant="ghost" disabled={connect.isPending} onClick={onClose}>
            Cancel
          </Button>
          <Button loading={connect.isPending} disabled={chosen.size === 0 || !list.isSuccess} onClick={submit}>
            {chosen.size > 1 ? `Connect ${chosen.size} Pages` : "Connect Page"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PageRow({ page, checked, onChange }: { page: FacebookPageOption; checked: boolean; onChange: (on: boolean) => void }) {
  const id = `facebook-page-${page.id}`;
  const name = page.name ?? page.username ?? "Facebook Page";
  return (
    <li>
      <label
        htmlFor={id}
        className={cn(
          "flex min-h-14 items-center gap-3 rounded-lg border border-line px-3 py-2",
          page.can_connect ? "cursor-pointer" : "cursor-not-allowed",
          checked && "border-brand-line bg-brand-soft",
        )}
      >
        <Checkbox
          id={id}
          checked={checked}
          disabled={!page.can_connect}
          onCheckedChange={(state) => onChange(state === true)}
          aria-describedby={page.problem ? `${id}-problem` : undefined}
        />
        <Avatar size="default">
          {page.picture_url ? <AvatarImage src={page.picture_url} alt="" /> : null}
          <AvatarFallback className="bg-brand-soft text-brand-fg">{name.slice(0, 1).toUpperCase()}</AvatarFallback>
        </Avatar>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{name}</span>
          {page.username ? <span className="block truncate text-xs text-fg-secondary">@{page.username}</span> : null}
          {page.problem ? (
            <span id={`${id}-problem`} className="block text-xs text-warning">
              {page.problem}
            </span>
          ) : null}
        </span>
        {page.connected ? <Badge tone="neutral">Connected</Badge> : null}
      </label>
    </li>
  );
}
