import { Info } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/states/EmptyState";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { instagramOnly } from "@/lib/copy";

/**
 * UI-064 (UI-ISS-081): automations answer comments and DMs on Instagram only, so a workspace with
 * no Instagram account (WhatsApp only, or nothing yet) hears that first, with the way to fix it.
 * `page` replaces the list's empty state; `inline` sits above the gallery's templates or a list.
 */
export function InstagramOnlyNotice({
  slug,
  variant,
  canConnect = true,
}: {
  slug: string;
  variant: "page" | "inline";
  /** Only owners and admins can connect an account; others are told whom to ask. */
  canConnect?: boolean;
}) {
  const href = `/w/${slug}/settings/connections` as Route;
  if (variant === "page") {
    return (
      <Card data-testid="instagram-only-notice">
        <EmptyState
          title={instagramOnly.title}
          body={instagramOnly.body}
          action={
            canConnect ? (
              <Button asChild size="lg">
                <Link href={href}>{instagramOnly.action}</Link>
              </Button>
            ) : (
              <p className="text-sm text-fg-secondary">{instagramOnly.ask}</p>
            )
          }
        />
      </Card>
    );
  }
  return (
    <Alert
      tone="brand"
      icon={<Info />}
      data-testid="instagram-only-notice"
      action={
        canConnect ? (
          <AlertAction asChild>
            <Link href={href}>{instagramOnly.action}</Link>
          </AlertAction>
        ) : null
      }
    >
      <AlertTitle>{instagramOnly.title}</AlertTitle>
      <AlertDescription>{canConnect ? instagramOnly.body : `${instagramOnly.body} ${instagramOnly.ask}`}</AlertDescription>
    </Alert>
  );
}
