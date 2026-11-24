"use client";

import type { Route } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { WidgetSettings } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { PLATFORM_LOGO_BG, PlatformGlyph } from "./PlatformGlyph";

const ABOUT = "A chat bubble for your website. Visitors' chats arrive in your inbox.";

function summary(settings: WidgetSettings | undefined): string {
  if (!settings || !settings.enabled) return ABOUT;
  const sites = settings.allowed_domains.length;
  if (sites === 0) return "No sites are allowed yet, so the chat won't show anywhere.";
  return `${sites} ${sites === 1 ? "site" : "sites"} · ${settings.conversations_today} ${settings.conversations_today === 1 ? "chat" : "chats"} today`;
}

/**
 * C-183: Website chat beside the other channels on Connections. `exists` is whether the workspace
 * has the channel: reading the settings creates it (services/widget/settings.ensure), so until then
 * nothing is read and the card offers Set up.
 */
export function WebsiteChatCard({
  href,
  exists,
  settings,
  loading,
}: {
  href: Route;
  exists: boolean;
  settings: WidgetSettings | undefined;
  loading: boolean;
}) {
  // Compact like the account cards (C-197): name and status, one summary line, then the action.
  const on = Boolean(settings?.enabled);
  return (
    <Card className="flex flex-col gap-2" role="article" aria-label="Website chat">
      <header className="flex items-start gap-3">
        <span aria-hidden className={cn("grid size-8 shrink-0 place-items-center rounded-lg text-on-brand", PLATFORM_LOGO_BG.web)}>
          <PlatformGlyph platform="web" className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">Website chat</p>
          {loading ? (
            <Skeleton className="mt-1 h-3.5 w-40" />
          ) : (
            <p className="truncate text-xs text-fg-secondary" title={summary(settings)}>
              {summary(settings)}
            </p>
          )}
        </div>
        {settings ? (
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-fg-secondary">
            <span className={cn("size-1.5 rounded-full", on ? "bg-success" : "bg-fg-disabled")} aria-hidden />
            {on ? "On" : "Off"}
          </span>
        ) : !exists ? (
          <Badge tone="neutral">Not set up</Badge>
        ) : null}
      </header>
      <div className="mt-1 flex items-center justify-end border-t border-line pt-3">
        <Button asChild variant="secondary" size="sm">
          <Link href={href}>{exists ? "Manage" : "Set up"}</Link>
        </Button>
      </div>
    </Card>
  );
}
