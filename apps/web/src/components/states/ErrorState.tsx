"use client";

import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/copy";
import { cn } from "@/lib/utils";

type Props = {
  error: unknown;
  onRetry?: () => void;
  /** Fill the viewport, for failures that stop the whole app (F-01: /v1/me failing). */
  fullPage?: boolean;
};

/** Says what happened and offers Retry. Never redirects (v1 looped back to sign-in). */
export function ErrorState({ error, onRetry, fullPage = false }: Props) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-10 text-center",
        fullPage && "min-h-dvh",
      )}
    >
      <AlertTriangle className="size-6 text-warning" aria-hidden />
      <p className="text-base font-semibold">This didn&apos;t load</p>
      <p className="max-w-md text-sm text-fg-secondary">{errorMessage(error)}</p>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          <RotateCw aria-hidden /> Try again
        </Button>
      ) : null}
    </div>
  );
}
