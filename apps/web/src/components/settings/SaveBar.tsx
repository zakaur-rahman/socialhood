"use client";

import { CheckCircle2, CircleAlert } from "lucide-react";
import { useEffect } from "react";

import { BOTTOM_BAR, reserveBottomBar } from "@/components/shell/sticky-bar";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

export const LEAVE_WARNING = "You have unsaved changes. Leave this page without saving them?";

/**
 * Warns before unsaved changes are lost (C-066): the browser's own prompt on reload, close or an
 * address typed in (beforeunload), and a confirm on any in-app link (the sidebar, the settings
 * tabs). Links are caught on the window in the capture phase, before Next's Link sees the click.
 * Links that open elsewhere (new tab, modified click, download, same page) pass through.
 */
export function useLeaveWarning(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const click = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target instanceof Element ? event.target : null;
      const anchor = target?.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      if ((anchor.target && anchor.target !== "_self") || anchor.hasAttribute("download")) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return; // leaving the app: beforeunload asks
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      if (window.confirm(LEAVE_WARNING)) return;
      event.preventDefault();
      event.stopPropagation();
    };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("click", click, true);
    };
  }, [dirty]);
}

/**
 * The sticky bar at the bottom of a settings form (C-066), in place of a Save button in the top
 * bar: "All changes saved" when clean; "Unsaved changes" with Reset and Save when dirty; a
 * spinner while saving; a failed save's error in place. While dirty, leaving warns first.
 * A page whose switches save as they change (Notifications) passes `dirty={false}` and gets the
 * saving and error states only.
 *
 * It floats (DESIGN_SYSTEM §6, level 1; D-12): the opaque `overlay` surface with a `line` ring and
 * `shadow-floating`, like a menu or a toast, no blur. It reserves its height so a focused control
 * is never under it, and stays in the flow on short viewports (UI-ISS-014, `shell/sticky-bar.ts`).
 */
export function SaveBar({
  dirty,
  saving,
  error,
  onReset,
  onSave,
}: {
  dirty: boolean;
  saving: boolean;
  error?: string | null;
  onReset?: () => void;
  onSave?: () => void;
}) {
  useLeaveWarning(dirty);
  const showActions = (dirty || saving) && onSave;
  return (
    <div
      ref={reserveBottomBar}
      role="region"
      aria-label="Save changes"
      className={cn("sticky bottom-0 z-20 pt-2 pb-4", BOTTOM_BAR)}
    >
      <div className="flex flex-col gap-3 rounded-xl bg-overlay px-4 py-3 ring-1 ring-line shadow-floating sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          <p role="status" aria-live="polite" className="flex min-h-6 items-center gap-2 text-sm font-medium">
            {saving ? (
              <>
                <Spinner className="text-brand-fg" />
                Saving…
              </>
            ) : dirty ? (
              <>
                <span className="size-2 shrink-0 rounded-full bg-warning" aria-hidden />
                Unsaved changes
              </>
            ) : error ? (
              <>
                <CircleAlert className="size-4 shrink-0 text-danger-fg" aria-hidden />
                Last change not saved
              </>
            ) : (
              <>
                <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />
                All changes saved
              </>
            )}
          </p>
          {error && !saving ? (
            <p role="alert" className="text-sm text-danger-fg">
              {error}
            </p>
          ) : null}
        </div>
        {showActions ? (
          <div className="flex gap-2">
            <Button
              type="button"
              variant="secondary"
              size="xl"
              className="flex-1 sm:flex-none"
              disabled={saving || !dirty}
              onClick={onReset}
            >
              Reset
            </Button>
            <Button
              type="button"
              size="xl"
              className="flex-1 sm:flex-none"
              disabled={saving || !dirty}
              onClick={onSave}
            >
              Save
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
