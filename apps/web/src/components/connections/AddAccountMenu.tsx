"use client";

import { ChevronDown, Plus } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

import { FacebookGlyph } from "./FacebookGlyph";
import { InstagramGlyph } from "./InstagramGlyph";
import { WhatsAppGlyph } from "./WhatsAppGlyph";

/**
 * Connections' one "Add account" button: a menu of the platforms that have a connect flow, each
 * with its mark and a line on what it connects. The actions are the page's own (the Instagram
 * OAuth start, the Facebook Page picker and the WhatsApp Embedded Signup hook); this only presents them. Platforms without a
 * backend aren't listed. Each mark sits on a tile in its platform's own logo colours.
 */
function LogoTile({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg text-on-brand", className)}>
      {children}
    </span>
  );
}

export function AddAccountMenu({
  onInstagram,
  onFacebook,
  onWhatsApp,
  whatsAppConfigured,
  busy,
}: {
  onInstagram: () => void;
  onFacebook: () => void;
  onWhatsApp: () => void;
  whatsAppConfigured: boolean;
  busy: boolean;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="lg" loading={busy}>
          <Plus aria-hidden />
          Add account
          <ChevronDown aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-64">
        <DropdownMenuItem onSelect={onInstagram} className="items-center gap-3 py-2">
          <LogoTile className="bg-instagram-logo-gradient">
            <InstagramGlyph className="size-4" />
          </LogoTile>
          <span className="flex flex-col">
            <span className="font-medium">Instagram</span>
            <span className="text-xs text-fg-secondary">Business or creator account, for DMs and comments</span>
          </span>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onFacebook} className="items-center gap-3 py-2">
          <LogoTile className="bg-facebook-logo">
            <FacebookGlyph className="size-4" />
          </LogoTile>
          <span className="flex flex-col">
            <span className="font-medium">Facebook</span>
            <span className="text-xs text-fg-secondary">A Facebook Page, for Messenger and comments</span>
          </span>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onWhatsApp} disabled={!whatsAppConfigured} className="items-center gap-3 py-2">
          <LogoTile className="bg-whatsapp-logo">
            <WhatsAppGlyph className="size-4" />
          </LogoTile>
          <span className="flex flex-col">
            <span className="font-medium">WhatsApp</span>
            <span className="text-xs text-fg-secondary">
              {whatsAppConfigured ? "A WhatsApp Business number" : "WhatsApp isn't set up for this app yet"}
            </span>
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
