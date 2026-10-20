"use client";

import { useReturnFocus } from "@/components/agent/use-return-focus";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { INBOX_SHORTCUTS } from "@/lib/inbox/shortcuts";
import { cn } from "@/lib/utils";

import { useSingleKeyShortcuts } from "./use-inbox-shortcuts";

/**
 * D-14, WCAG 2.1.4: the inbox's single-key shortcuts, and the per-device switch that turns them
 * off. Opened by the keyboard button in the list header and by "?". Focus returns to what opened it.
 */
export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [enabled, setEnabled] = useSingleKeyShortcuts();
  // Opened by a button or a key, not a Radix trigger: remember what had focus and return it on close.
  const returnFocus = useReturnFocus();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md" {...returnFocus}>
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Single keys work in the inbox when you are not typing in a field.</DialogDescription>
        </DialogHeader>

        <div className="flex items-start justify-between gap-4 rounded-lg border border-line-subtle bg-field p-3">
          <div className="min-w-0 space-y-0.5">
            <Label htmlFor="single-key-shortcuts" className="text-sm font-medium">
              Single-key shortcuts
            </Label>
            <p id="single-key-shortcuts-hint" className="text-xs text-fg-secondary">
              On this device. Turn them off if a letter key ever acts by accident, for example with speech input.
              Shortcuts with Ctrl or ⌘, such as Ctrl K for Ask Social Hood, keep working.
            </p>
          </div>
          <Switch
            id="single-key-shortcuts"
            checked={enabled}
            onCheckedChange={setEnabled}
            aria-describedby="single-key-shortcuts-hint"
            className="mt-0.5"
          />
        </div>

        <dl
          aria-label="Shortcuts"
          data-enabled={enabled}
          className={cn("grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-sm", !enabled && "text-fg-secondary")}
        >
          {INBOX_SHORTCUTS.map((shortcut) => (
            <div key={shortcut.label} className="contents">
              <dt className="flex gap-1">
                {shortcut.keys.map((key) => (
                  <kbd
                    key={key}
                    className="inline-flex h-6 min-w-6 items-center justify-center rounded-md border border-line bg-field px-1.5 font-mono text-xs text-fg"
                  >
                    {key}
                  </kbd>
                ))}
              </dt>
              <dd>{shortcut.label}</dd>
            </div>
          ))}
        </dl>
        {!enabled ? (
          <p className="text-xs text-fg-secondary">
            Single-key shortcuts are off. Only Esc and shortcuts with Ctrl or ⌘ work.
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
