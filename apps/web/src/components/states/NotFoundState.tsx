import { SearchX } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/states/EmptyState";

/**
 * A page's main resource is gone (the API said 404): "This post doesn't exist or was deleted",
 * with a way back to its list. One wording for a deleted resource and one in another workspace,
 * so it never reveals that something exists elsewhere. Other API errors keep ErrorState.
 */
export function NotFoundState({
  thing,
  backHref,
  backLabel,
  size = "default",
  className = "flex-1",
}: {
  /** Lower case, singular: "post", "conversation". */
  thing: string;
  backHref: Route;
  /** "Back to Schedule". */
  backLabel: string;
  size?: "default" | "compact";
  className?: string;
}) {
  return (
    <EmptyState
      size={size}
      className={className}
      icon={<SearchX aria-hidden />}
      title={`This ${thing} doesn't exist or was deleted`}
      body="Check the link, or go back to the list."
      action={
        <Link href={backHref} className="text-sm text-brand-fg underline-offset-4 hover:underline">
          {backLabel}
        </Link>
      }
    />
  );
}
