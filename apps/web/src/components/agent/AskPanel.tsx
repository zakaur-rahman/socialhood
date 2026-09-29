"use client";

import { Maximize2, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useSyncExternalStore } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { modifierKey } from "@/lib/agent/format";
import { askHref, isAskPage } from "@/lib/agent/routes";
import { useAskStore } from "@/lib/agent/store";
import { useNow } from "@/lib/use-browser-state";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AskConversation } from "./AskConversation";
import { NewThreadButton, ThreadMenu } from "./Threads";
import { ASK_SHORTCUT_ARIA, useAskShortcut } from "./use-ask-shortcut";
import { useReturnFocus } from "./use-return-focus";

export const PANEL_COMPOSER_ID = "ask-panel-question";
export const PAGE_COMPOSER_ID = "ask-page-question";

function focusComposer(id: string) {
  document.getElementById(id)?.focus();
}

const noSubscribe = () => () => {};

/** "Ctrl" or "⌘", read after hydration (the server assumes Ctrl). */
function useModifierKey(): "Ctrl" | "⌘" {
  return useSyncExternalStore(
    noSubscribe,
    () => modifierKey(typeof navigator === "undefined" ? undefined : navigator.platform || navigator.userAgent),
    () => "Ctrl",
  );
}

/**
 * FR-AGT-01: the panel on every page and its Ctrl/⌘ K shortcut. The workspace layout's shell
 * mounts it once. On the Ask page itself the shortcut focuses that page's question box.
 */
export function AskRoot() {
  const open = useAskStore((state) => state.open);
  const setOpen = useAskStore((state) => state.setOpen);
  const onAskPage = isAskPage(usePathname());

  useAskShortcut(() => {
    if (open) {
      setOpen(false);
      return;
    }
    if (onAskPage) {
      focusComposer(PAGE_COMPOSER_ID);
      return;
    }
    // Another dialog is open: its keys win.
    if (document.querySelector('[role="dialog"], [role="alertdialog"]')) return;
    setOpen(true);
  });

  return <AskPanel />;
}

/**
 * The Ask Social Hood side sheet: 420 px on the right from 768 px, the full screen on phones. It
 * traps focus, closes on Esc and returns focus to what opened it (UX-A11Y-02).
 */
export function AskPanel() {
  const workspace = useCurrentWorkspace();
  const open = useAskStore((state) => state.open);
  const setOpen = useAskStore((state) => state.setOpen);
  const now = useNow();
  const close = () => setOpen(false);
  const returnFocus = useReturnFocus();

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 duration-200 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0 motion-reduce:animate-none" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          onOpenAutoFocus={(event) => {
            returnFocus.onOpenAutoFocus();
            event.preventDefault();
            focusComposer(PANEL_COMPOSER_ID);
          }}
          onCloseAutoFocus={returnFocus.onCloseAutoFocus}
          className="fixed inset-0 z-50 flex flex-col bg-panel shadow-xl outline-none duration-200 data-open:animate-in data-open:slide-in-from-right-10 data-closed:animate-out data-closed:slide-out-to-right-10 motion-reduce:animate-none md:inset-y-0 md:right-0 md:left-auto md:w-[420px] md:border-l md:border-line"
          data-testid="ask-panel"
        >
          <header className="flex h-14 shrink-0 items-center gap-1 border-b border-line pr-2 pl-4">
            <Sparkles className="size-4 shrink-0 text-brand-fg" aria-hidden />
            <DialogPrimitive.Title className="ml-1 min-w-0 flex-1 truncate text-base font-semibold">
              Ask Social Hood
            </DialogPrimitive.Title>
            <NewThreadButton wid={workspace.id} iconOnly onStart={() => focusComposer(PANEL_COMPOSER_ID)} />
            <ThreadMenu wid={workspace.id} now={now} />
            <Button asChild variant="ghost" size="icon" className="size-10 text-fg-secondary md:size-8">
              <Link href={askHref(workspace.slug)} onClick={close} aria-label="Open the Ask page">
                <Maximize2 aria-hidden />
              </Link>
            </Button>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="icon" className="size-10 text-fg-secondary md:size-8" aria-label="Close">
                <X aria-hidden />
              </Button>
            </DialogPrimitive.Close>
          </header>
          <AskConversation composerId={PANEL_COMPOSER_ID} onNavigate={close} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/**
 * Opens Ask Social Hood: an item under the logo in the sidebar (desktop), an icon in the phone
 * top bar. On the Ask page it focuses the question box.
 */
export function AskButton({ variant, collapsed = false }: { variant: "sidebar" | "topbar"; collapsed?: boolean }) {
  const setOpen = useAskStore((state) => state.setOpen);
  const onAskPage = isAskPage(usePathname());
  const key = useModifierKey();
  const activate = () => (onAskPage ? focusComposer(PAGE_COMPOSER_ID) : setOpen(true));

  if (variant === "topbar") {
    return (
      <button
        type="button"
        onClick={activate}
        aria-label="Ask Social Hood"
        aria-keyshortcuts={ASK_SHORTCUT_ARIA}
        className="grid size-10 shrink-0 place-items-center rounded-lg text-brand-fg hover:bg-white/5"
      >
        <Sparkles className="size-5" aria-hidden />
      </button>
    );
  }

  const button = (
    <button
      type="button"
      onClick={activate}
      aria-label={collapsed ? "Ask Social Hood" : undefined}
      aria-keyshortcuts={ASK_SHORTCUT_ARIA}
      className={cn(
        "relative flex w-full items-center gap-3 rounded-lg border border-brand-line bg-brand-soft px-3 py-2 text-left text-[15px] font-medium text-fg hover:bg-brand-line",
        collapsed && "size-10 justify-center px-0 py-0",
      )}
    >
      <Sparkles className="size-5 shrink-0 text-brand-fg" aria-hidden />
      {collapsed ? null : <span className="min-w-0 flex-1 truncate">Ask Social Hood</span>}
    </button>
  );
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right">{collapsed ? `Ask Social Hood (${key} K)` : `${key} K`}</TooltipContent>
    </Tooltip>
  );
}
