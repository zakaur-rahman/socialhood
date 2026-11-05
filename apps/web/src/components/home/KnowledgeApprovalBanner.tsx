import { BookOpen } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { waitingTitle } from "@/lib/knowledge/approval";

/**
 * Only while sources an AI app added are waiting. The API counts them only for roles that can
 * approve them, so everyone else's count is 0. The approving happens on the Knowledge page.
 */
export function KnowledgeApprovalBanner({ count, slug }: { count: number; slug: string }) {
  if (count <= 0) return null;
  return (
    <Alert
      tone="warning"
      variant="outline"
      aria-labelledby="home-approvals"
      data-testid="approval-banner"
      icon={<BookOpen />}
      action={
        <AlertAction asChild>
          <Link href={`/w/${slug}/knowledge` as Route}>Review</Link>
        </AlertAction>
      }
    >
      <AlertTitle>
        <h2 id="home-approvals">{waitingTitle(count)}</h2>
      </AlertTitle>
      <AlertDescription className="text-xs">
        Your AI won&apos;t use {count === 1 ? "it until it's" : "them until they're"} approved.
      </AlertDescription>
    </Alert>
  );
}
