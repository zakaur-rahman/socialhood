"use client";

import { CheckCircle2 } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";

/**
 * D-08: the inline status of a settings page whose controls save as they change (Notifications):
 * "Saving…" while a change is in flight, then "Saved" until the next one. Nothing before the first
 * change. A failed change is the save bar's (it shows only on failure). The live region is always
 * present so a screen reader hears the words appear.
 */
export function AutosaveStatus({ saving, saved }: { saving: boolean; saved: boolean }) {
  return (
    <p role="status" aria-live="polite" className="flex items-center gap-1.5 text-sm text-fg-secondary empty:hidden">
      {saving ? (
        <>
          <Spinner className="text-brand-fg" />
          Saving…
        </>
      ) : saved ? (
        <>
          <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />
          Saved
        </>
      ) : null}
    </p>
  );
}
