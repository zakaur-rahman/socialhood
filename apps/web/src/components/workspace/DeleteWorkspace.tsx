"use client";

import { TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { SettingsCard } from "@/components/settings/SettingsCard";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import { useDeleteWorkspace } from "@/lib/api/queries/workspaceDeletion";
import { errorMessage } from "@/lib/copy";
import { useCurrentWorkspace } from "@/lib/workspace";

/** What deleting removes (FR-ACC-05, F-16), in the order an owner would look for it. */
export const DELETED_DATA = [
  "Connected Instagram and WhatsApp accounts, which stop sending and receiving at once",
  "Conversations, messages, comments and contacts",
  "Automations, scheduled messages and scheduled posts",
  "The knowledge base, AI settings and Ask Social Hood history",
  "Uploaded photos, videos and files",
  "Analytics, notifications and usage",
] as const;

/**
 * Settings → Workspace danger zone (FR-ACC-05, F-16): owners only. The owner types the
 * workspace's name to confirm; a paid plan is cancelled, everything is erased within 24 hours,
 * and the owner goes to /app (another workspace, or a new one when this was their last).
 * C-066: shown as the red-accented danger card; the behaviour is unchanged.
 */
export function DeleteWorkspace() {
  const current = useCurrentWorkspace();
  if (current.role !== "owner") return null;
  return <DangerZone id={current.id} name={current.name} />;
}

function DangerZone({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  const remove = useDeleteWorkspace(id);
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const matches = typed.trim() === name.trim();

  const onOpenChange = (next: boolean) => {
    if (remove.isPending) return;
    setOpen(next);
    if (next) {
      setTyped("");
      setFieldError(null);
    }
  };

  const confirm = () => {
    if (!matches || remove.isPending) return;
    remove.mutate(typed, {
      onSuccess: () => {
        toast.success(`${name} was deleted`);
        router.replace("/app");
      },
      onError: (error) => {
        const field = error instanceof ApiError ? error.errors.find((e) => e.field === "confirm_name") : undefined;
        if (field) setFieldError(field.message);
        else toast.error(errorMessage(error));
      },
    });
  };

  return (
    <SettingsCard
      id="danger-zone"
      tone="danger"
      icon={<TriangleAlert />}
      label="Danger zone"
      title="Delete workspace"
      description={
        <>
          Permanently deletes {name} and everything in it. Any paid plan is cancelled right away, so you
          won&apos;t be charged again. This can&apos;t be undone.
        </>
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-fg-secondary">Only the owner can delete a workspace.</p>
        <AlertDialog open={open} onOpenChange={onOpenChange}>
          <AlertDialogTrigger asChild>
            <Button
              variant="outline"
              className="min-h-10 border-danger/60 px-4 text-danger-fg hover:bg-danger/10 hover:text-danger-fg"
            >
              Delete workspace
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent className="border-line bg-panel">
            <AlertDialogHeader>
              <AlertDialogTitle>Delete {name}?</AlertDialogTitle>
              <AlertDialogDescription asChild>
                <div className="space-y-3 text-sm text-fg-secondary">
                  <p>Everyone loses access now. Within 24 hours we permanently erase:</p>
                  <ul className="list-disc space-y-1 pl-5">
                    {DELETED_DATA.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <p>Your paid plan, if any, is cancelled now. This can&apos;t be undone.</p>
                </div>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <form
              noValidate
              className="space-y-1.5"
              onSubmit={(event) => {
                event.preventDefault();
                confirm();
              }}
            >
              <Label htmlFor="confirm-name">
                Type <span className="font-semibold text-fg">{name}</span> to confirm
              </Label>
              <Input
                id="confirm-name"
                autoComplete="off"
                spellCheck={false}
                value={typed}
                aria-invalid={!!fieldError}
                aria-describedby={fieldError ? "confirm-name-error" : undefined}
                onChange={(event) => {
                  setTyped(event.target.value);
                  setFieldError(null);
                }}
              />
              {fieldError ? (
                <p id="confirm-name-error" role="alert" className="text-sm text-danger-fg">
                  {fieldError}
                </p>
              ) : null}
            </form>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
              <Button
                type="button"
                disabled={!matches || remove.isPending}
                onClick={confirm}
                className="bg-danger-fill text-white hover:bg-danger-fill/90"
              >
                {remove.isPending ? "Deleting…" : "Delete workspace"}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </SettingsCard>
  );
}
