"use client";

import { Maximize2, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore, type CSSProperties } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { modifierKey } from "@/lib/agent/format";
import { askHref, isAskPage } from "@/lib/agent/routes";
import { useAskStore } from "@/lib/agent/store";
import { useNow } from "@/lib/use-browser-state";
import { usePaneWidth, type PaneWidthLimits } from "@/lib/use-pane-width";
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
 * The Ask Amplychat side sheet: 420 px on the right from 768 px, the full screen on phones. It
 * traps focus, closes on Esc and returns focus to what opened it (UX-A11Y-02). Its surface is the
 * sheets' (DESIGN_SYSTEM §6, level 2; D-12): `overlay` with `shadow-overlay` and a `line` edge,
 * over the modal scrim. It is a `SheetContent size="panel"`, so it moves like every sheet.
 */
/** The panel is resizable from its left edge on md and up (UI-078), remembered per device. */
const PANEL_LIMITS: PaneWidthLimits = { fallback: 420, min: 360, max: 720 };

export function AskPanel() {
  const [panelWidth, setPanelWidth, resetPanelWidth] = usePaneWidth("ask-panel", PANEL_LIMITS);
  const workspace = useCurrentWorkspace();
  const open = useAskStore((state) => state.open);
  const setOpen = useAskStore((state) => state.setOpen);
  const now = useNow();
  const close = () => setOpen(false);
  const returnFocus = useReturnFocus();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent
        size="panel"
        showCloseButton={false}
        aria-describedby={undefined}
        onOpenAutoFocus={(event) => {
          returnFocus.onOpenAutoFocus();
          event.preventDefault();
          focusComposer(PANEL_COMPOSER_ID);
        }}
        onCloseAutoFocus={returnFocus.onCloseAutoFocus}
        className="gap-0 md:w-(--pane-w) md:max-w-[90vw]"
        style={{ "--pane-w": `${panelWidth}px` } as CSSProperties}
        data-testid="ask-panel"
      >
        <ResizeHandle
          edge="start"
          label="Resize the Ask panel"
          value={panelWidth}
          min={PANEL_LIMITS.min}
          max={PANEL_LIMITS.max}
          onChange={setPanelWidth}
          onReset={resetPanelWidth}
        />
        <header className="flex h-14 shrink-0 items-center gap-1 border-b border-line pr-2 pl-4">
          <Sparkles className="size-4 shrink-0 text-brand-fg" aria-hidden />
          <SheetTitle className="ml-1 min-w-0 flex-1 truncate text-base font-semibold">
            Ask Amplychat
          </SheetTitle>
          <NewThreadButton wid={workspace.id} iconOnly onStart={() => focusComposer(PANEL_COMPOSER_ID)} />
          <ThreadMenu wid={workspace.id} now={now} />
          <Button asChild variant="ghost" size="icon" className="text-fg-secondary">
            <Link href={askHref(workspace.slug)} onClick={close} aria-label="Open the Ask page">
              <Maximize2 aria-hidden />
            </Link>
          </Button>
          <Button variant="ghost" size="icon" className="text-fg-secondary" aria-label="Close" onClick={close}>
            <X aria-hidden />
          </Button>
        </header>
        <AskConversation composerId={PANEL_COMPOSER_ID} onNavigate={close} />
      </SheetContent>
    </Sheet>
  );
}

/**
 * Opens Ask Amplychat: an item under the logo in the sidebar (desktop), an icon in the phone
 * top bar. On the Ask page it focuses the question box.
 */
export function AskButton({ variant, collapsed = false }: { variant: "sidebar" | "topbar"; collapsed?: boolean }) {
  const setOpen = useAskStore((state) => state.setOpen);
  const onAskPage = isAskPage(usePathname());
  const key = useModifierKey();
  const panelOpen = useAskStore((state) => state.open);
  const [hint, setHint] = useState(false);
  const activate = () => (onAskPage ? focusComposer(PAGE_COMPOSER_ID) : setOpen(true));

  if (variant === "topbar") {
    return (
      <button
        type="button"
        onClick={activate}
        aria-label="Ask Amplychat"
        aria-keyshortcuts={ASK_SHORTCUT_ARIA}
        className="grid size-10 shrink-0 place-items-center rounded-lg text-brand-fg hover:bg-hover"
      >
        <Sparkles className="size-5" aria-hidden />
      </button>
    );
  }

  const button = (
    <button
      type="button"
      onClick={activate}
      aria-label={collapsed ? "Ask Amplychat" : undefined}
      aria-keyshortcuts={ASK_SHORTCUT_ARIA}
      className={cn(
        "relative flex w-full items-center gap-3 rounded-lg border border-brand-line bg-brand-soft px-3 py-2 text-left text-md font-medium text-fg hover:bg-brand-soft-hover",
        collapsed && "size-10 justify-center px-0 py-0",
      )}
    >
      <Sparkles className="size-5 shrink-0 text-brand-fg" aria-hidden />
      {collapsed ? null : <span className="min-w-0 flex-1 truncate">Ask Amplychat</span>}
    </button>
  );
  // The hint stays shut while the panel is open: a tooltip is a dismiss layer, and one that opens
  // under a resting pointer would take the panel's Esc. Its content is not even mounted then: a
  // closing tooltip lingers for its exit animation, and a layer left over from the button's focus
  // (after the panel closed) can end up above the panel's and swallow its first Esc.
  return (
    <Tooltip open={hint && !panelOpen} onOpenChange={setHint}>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      {panelOpen ? null : (
        <TooltipContent side="right">{collapsed ? `Ask Amplychat (${key} K)` : `${key} K`}</TooltipContent>
      )}
    </Tooltip>
  );
}
