"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useAiSettings } from "@/lib/api/queries";
import { BUILT_IN_ESCALATIONS, takeoverText } from "@/lib/ai/format";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * F-09: before Auto is turned on (an account or one conversation), say what Auto does and list
 * the escalation rules, the owner's phrases included when they can be read (admins).
 */
export function AutoConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  target,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  /** "this conversation" or "@maple.bakery". */
  target: string;
}) {
  const workspace = useCurrentWorkspace();
  const settings = useAiSettings(workspace.id, open && workspace.role !== "agent");
  const phrases = settings.data?.escalation_phrases ?? [];
  const takeover = settings.data ? takeoverText(settings.data.takeover_minutes) : "for the takeover period in Settings → AI";

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="border-line bg-panel sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Turn on Auto for {target}?</AlertDialogTitle>
          <AlertDialogDescription className="text-fg-secondary">
            The AI sends replies on its own when it&apos;s confident and the answer is in your knowledge. Otherwise it
            leaves a suggested reply and marks the conversation Needs you.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2 text-sm">
          <p className="font-medium">It hands the conversation to you when:</p>
          <ul className="list-disc space-y-1 pl-5 text-fg-secondary" aria-label="Escalation rules">
            {BUILT_IN_ESCALATIONS.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
            <li>
              {phrases.length > 0
                ? `A message has one of your escalation phrases: ${phrases.map((p) => `“${p}”`).join(", ")}`
                : "A message has one of your escalation phrases"}
            </li>
          </ul>
          <p className="text-fg-secondary">When you reply yourself, Auto pauses in that conversation {takeover}.</p>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction className="bg-brand-gradient text-white" onClick={onConfirm}>
            Turn on Auto
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// The upgrade dialog (entitlement_required, quota_exceeded) is components/billing/UpgradeDialog:
// every 402 opens it (T8.4).
