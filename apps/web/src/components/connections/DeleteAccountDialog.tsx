"use client";

import { useState } from "react";

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
import type { SocialAccount } from "@/lib/api/types";

export type DeleteMode = "disconnect" | "remove";

/** What deleting an account's data removes, and what stays (C-067). */
export const DELETED_FOR_ACCOUNT = [
  "Its conversations, messages and contacts",
  "Its comments, posts and post stats",
  "Automations for this account, and its scheduled messages and posts",
  "Photos and files received or sent in its messages",
] as const;

export const KEPT_FOR_ACCOUNT = [
  "Your knowledge base and AI settings",
  "Workspace settings, members and billing",
  "Your other accounts and their data",
] as const;

/** What the member types: the handle, else the number, else the name (as the API asks). */
export function confirmationTarget(account: SocialAccount): string {
  if (account.username) return `@${account.username}`;
  return account.phone_number ?? account.display_name ?? "this account";
}

const digits = (value: string) => value.replace(/\D/g, "");

/** The handle with or without "@" in any case, or the number with any spacing or "+". */
export function confirms(account: SocialAccount, typed: string): boolean {
  const given = typed.trim();
  if (!given) return false;
  if (account.username && given.replace(/^@+/, "").toLowerCase() === account.username.toLowerCase()) return true;
  if (account.phone_number && digits(given) !== "" && digits(given) === digits(account.phone_number)) return true;
  return given.toLowerCase() === confirmationTarget(account).toLowerCase();
}

const COPY: Record<DeleteMode, { trigger: string; action: string; title: (handle: string) => string; lead: (handle: string) => string }> = {
  disconnect: {
    trigger: "Disconnect and delete data",
    action: "Disconnect and delete",
    title: (handle) => `Disconnect ${handle} and delete its data?`,
    lead: (handle) =>
      `Social Hood disconnects ${handle} now, then permanently deletes everything stored for it. This can't be undone.`,
  },
  remove: {
    trigger: "Remove",
    action: "Remove account",
    title: (handle) => `Remove ${handle}?`,
    lead: (handle) => `Social Hood permanently deletes ${handle} and everything stored for it. This can't be undone.`,
  },
};

/**
 * C-067: Disconnect and delete data (a connected account) and Remove (a disconnected or sandbox
 * one) share this dialog: what goes and what stays, then the account's handle or number typed to
 * confirm. `onConfirm` resolves once the API accepted it; a 422 on `confirm` shows under the field.
 */
export function DeleteAccountDialog({
  account,
  handle,
  mode,
  pending,
  onConfirm,
}: {
  account: SocialAccount;
  handle: string;
  mode: DeleteMode;
  pending: boolean;
  onConfirm: (confirm: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const copy = COPY[mode];
  const target = confirmationTarget(account);
  const matches = confirms(account, typed);
  const inputId = `confirm-delete-${account.id}`;

  const onOpenChange = (next: boolean) => {
    if (pending) return;
    setOpen(next);
    if (next) {
      setTyped("");
      setFieldError(null);
    }
  };

  const submit = async () => {
    if (!matches || pending) return;
    try {
      await onConfirm(typed.trim());
      setOpen(false);
    } catch (error) {
      const field = error instanceof ApiError ? error.errors.find((e) => e.field === "confirm") : undefined;
      if (field) setFieldError(field.message);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogTrigger asChild>
        <Button variant="destructive-ghost" size="lg">
          {copy.trigger}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{copy.title(handle)}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>{copy.lead(handle)}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <section aria-label="Deleted" className="rounded-lg border border-danger/30 p-3">
                  <p className="font-medium text-fg">Deleted</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4">
                    {DELETED_FOR_ACCOUNT.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
                <section aria-label="Kept" className="rounded-lg border border-line p-3">
                  <p className="font-medium text-fg">Kept</p>
                  <ul className="mt-1 list-disc space-y-1 pl-4">
                    {KEPT_FOR_ACCOUNT.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <form
          noValidate
          className="space-y-1.5"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <Label htmlFor={inputId}>
            Type <span className="font-semibold text-fg">{target}</span> to confirm
          </Label>
          <Input
            id={inputId}
            autoComplete="off"
            spellCheck={false}
            value={typed}
            aria-invalid={!!fieldError}
            aria-describedby={fieldError ? `${inputId}-error` : undefined}
            onChange={(event) => {
              setTyped(event.target.value);
              setFieldError(null);
            }}
          />
          {fieldError ? (
            <p id={`${inputId}-error`} role="alert" className="text-sm text-danger-fg">
              {fieldError}
            </p>
          ) : null}
        </form>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <Button type="button" variant="destructive" disabled={!matches || pending} onClick={() => void submit()}>
            {pending ? "Deleting…" : copy.action}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
