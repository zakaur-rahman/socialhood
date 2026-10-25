"use client";

import { House, Inbox, Sparkles } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useParams } from "next/navigation";

import { NotFoundPage } from "@/components/not-found/NotFoundPage";
import { Button } from "@/components/ui/button";

/**
 * A page that doesn't exist inside a workspace: unknown sub-addresses (`[...rest]`) and
 * `notFound()` from a page. It renders inside the workspace layout, so the sidebar stays, and it
 * offers this workspace's Home, Inbox and Ask.
 */
export default function WorkspaceNotFound() {
  const { slug } = useParams<{ slug: string }>();
  const base = `/w/${slug}`;
  return (
    <NotFoundPage className="flex-1">
      <Button asChild size="lg">
        <Link href={`${base}/home` as Route}>
          <House aria-hidden /> Go to Home
        </Link>
      </Button>
      <Button asChild variant="secondary" size="lg">
        <Link href={`${base}/inbox` as Route}>
          <Inbox aria-hidden /> Open Inbox
        </Link>
      </Button>
      <Button asChild variant="ghost" size="lg">
        <Link href={`${base}/ask` as Route}>
          <Sparkles aria-hidden /> Ask
        </Link>
      </Button>
    </NotFoundPage>
  );
}
