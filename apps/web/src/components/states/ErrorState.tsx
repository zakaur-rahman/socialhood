"use client";

import { AlertTriangle, House, RotateCw } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/copy";
import { cn } from "@/lib/utils";

type Props = {
  error: unknown;
  onRetry?: () => void;
  /**
   * Where "Go to Home" leads, beside Try again (UX-011): the workspace's Home. Leave it out where
   * Home isn't a way out (on Home itself, or before a workspace is known).
   */
  homeHref?: Route;
  /**
   * `default`: centred, for a page or a pane. `compact`: left-aligned 14 px text and small buttons,
   * for a block inside a card, a list or a dialog (DESIGN_SYSTEM §8.2).
   */
  size?: "default" | "compact";
  /** Fill the viewport, for failures that stop the whole app (F-01: /v1/me failing). */
  fullPage?: boolean;
  className?: string;
};

/**
 * Says what happened and offers Try again, and Go to Home where given. Never redirects (v1
 * looped back to sign-in). The buttons are Button's ladder (`default`, or `sm` when compact), so
 * they are 40 px on coarse pointers.
 */
export function ErrorState({ error, onRetry, homeHref, size = "default", fullPage = false, className }: Props) {
  const compact = size === "compact";
  const buttonSize = compact ? "sm" : "default";
  const actions =
    onRetry || homeHref ? (
      <div className={cn("flex flex-wrap items-center gap-2", compact ? "mt-1" : "justify-center")}>
        {onRetry ? (
          <Button variant="secondary" size={buttonSize} onClick={onRetry}>
            <RotateCw aria-hidden /> Try again
          </Button>
        ) : null}
        {homeHref ? (
          <Button asChild variant="ghost" size={buttonSize}>
            <Link href={homeHref}>
              <House aria-hidden /> Go to Home
            </Link>
          </Button>
        ) : null}
      </div>
    ) : null;

  if (compact) {
    return (
      <div role="alert" data-size="compact" className={cn("flex items-start gap-2 text-left text-sm", className)}>
        <span className="flex h-5 shrink-0 items-center" aria-hidden>
          <AlertTriangle className="size-4 text-warning" />
        </span>
        <div className="flex min-w-0 flex-col items-start gap-1">
          <p className="font-semibold">This didn&apos;t load</p>
          <p className="text-fg-secondary">{errorMessage(error)}</p>
          {actions}
        </div>
      </div>
    );
  }

  return (
    <div
      role="alert"
      data-size="default"
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-10 text-center",
        fullPage && "min-h-dvh",
        className,
      )}
    >
      <AlertTriangle className="size-6 text-warning" aria-hidden />
      <p className="text-base font-semibold">This didn&apos;t load</p>
      <p className="max-w-md text-sm text-fg-secondary">{errorMessage(error)}</p>
      {actions}
    </div>
  );
}
