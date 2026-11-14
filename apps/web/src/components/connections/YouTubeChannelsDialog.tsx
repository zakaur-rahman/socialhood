"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useConnectYouTubeChannels, useYouTubeChannels } from "@/lib/api/queries";
import type { YouTubeChannel } from "@/lib/api/types";
import { youtubeConnected, youtubeListError } from "@/lib/copy";
import { toastError } from "@/lib/toast-error";
import { cn } from "@/lib/utils";

/**
 * After Google sign-in, the channels of that Google account, to pick one from. A workspace has one
 * YouTube channel, so this is a single choice; a channel already connected is listed but can't be
 * picked. The nonce (from the callback's ?youtube=) is spent when the channel connects, so a refusal
 * (the plan's limit) leaves the list open.
 */
export function YouTubeChannelsDialog({
  wid,
  nonce,
  onClose,
}: {
  wid: string;
  /** The nonce to list channels with; null: closed. */
  nonce: string | null;
  onClose: () => void;
}) {
  const list = useYouTubeChannels(wid);
  const connect = useConnectYouTubeChannels(wid);
  const [picked, setPicked] = useState<string | null>(null);
  const { mutate: load } = list;

  useEffect(() => {
    if (nonce) load(nonce);
  }, [nonce, load]);

  const channels = list.data?.items ?? [];
  const open = channels.filter((channel) => !channel.connected);
  // The only channel left to connect is chosen already, so one click finishes.
  const chosen = picked ?? (open.length === 1 ? open[0].channel_id : null);

  const submit = () => {
    if (!nonce || !chosen) return;
    const channel = channels.find((item) => item.channel_id === chosen);
    connect.mutate(
      { nonce, channelIds: [chosen] },
      {
        onSuccess: () => {
          toast.success(youtubeConnected(channel?.title ?? "your channel"));
          onClose();
        },
        // Over the plan's limit (402): the upgrade dialog says so, and the list stays.
        onError: (error) => toastError(error),
      },
    );
  };

  return (
    <Dialog open={nonce !== null} onOpenChange={(isOpen) => (isOpen || connect.isPending ? undefined : onClose())}>
      <DialogContent data-testid="youtube-channels-dialog">
        <DialogHeader>
          <DialogTitle>Choose your YouTube channel</DialogTitle>
          <DialogDescription>
            Amplychat posts videos to the channel you pick. You can disconnect it later.
          </DialogDescription>
        </DialogHeader>
        {list.isPending || list.isIdle ? (
          <div role="status" aria-busy="true" aria-label="Loading your channels" className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : list.isError ? (
          <p role="alert" className="text-sm text-danger-fg">
            {youtubeListError(list.error)}
          </p>
        ) : channels.length === 0 ? (
          <p className="text-sm text-fg-secondary">
            This Google account has no YouTube channel. Create one on YouTube, then connect again.
          </p>
        ) : (
          <ul role="radiogroup" className="max-h-80 space-y-2 overflow-y-auto" aria-label="Your YouTube channels">
            {channels.map((channel) => (
              <ChannelRow
                key={channel.channel_id}
                channel={channel}
                checked={chosen === channel.channel_id}
                onChange={() => setPicked(channel.channel_id)}
              />
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button variant="ghost" disabled={connect.isPending} onClick={onClose}>
            Cancel
          </Button>
          <Button loading={connect.isPending} disabled={!chosen || !list.isSuccess} onClick={submit}>
            Connect channel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ChannelRow({ channel, checked, onChange }: { channel: YouTubeChannel; checked: boolean; onChange: () => void }) {
  const id = `youtube-channel-${channel.channel_id}`;
  return (
    <li>
      <label
        htmlFor={id}
        className={cn(
          "flex min-h-14 items-center gap-3 rounded-lg border border-line px-3 py-2",
          channel.connected ? "cursor-not-allowed" : "cursor-pointer",
          checked && "border-line-strong bg-raised",
        )}
      >
        <input
          id={id}
          type="radio"
          name="youtube-channel"
          className="size-4 accent-brand"
          checked={checked}
          disabled={channel.connected}
          onChange={onChange}
        />
        <Avatar size="default">
          {channel.avatar_url ? <AvatarImage src={channel.avatar_url} alt="" /> : null}
          <AvatarFallback className="bg-raised text-fg">{channel.title.slice(0, 1).toUpperCase()}</AvatarFallback>
        </Avatar>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{channel.title}</span>
          {channel.handle ? (
            <span className="block truncate text-xs text-fg-secondary">
              {channel.handle.startsWith("@") ? channel.handle : `@${channel.handle}`}
            </span>
          ) : null}
        </span>
        {channel.connected ? <Badge tone="neutral">Connected</Badge> : null}
      </label>
    </li>
  );
}
