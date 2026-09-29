"use client";

import { History, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { agentSettingsHref } from "@/lib/agent/routes";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AskConversation } from "./AskConversation";
import { PAGE_COMPOSER_ID } from "./AskPanel";
import { NewThreadButton, ThreadList, ThreadMenu } from "./Threads";

/**
 * /w/[slug]/ask (FR-AGT-01): Ask Social Hood as a full page. Thread history on the left from
 * 1024 px (a menu below that); the conversation and the question box in one centred, readable
 * column. It shows the same thread as the panel.
 */
export function AskPage() {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const admin = workspace.role !== "agent";
  const focus = () => document.getElementById(PAGE_COMPOSER_ID)?.focus();

  return (
    <div
      className="flex h-[calc(100dvh-56px)] overflow-hidden bg-canvas md:mx-4 md:mt-4 md:h-[calc(100dvh-32px)] md:rounded-xl md:border md:border-line"
      data-testid="ask-page"
    >
      <aside aria-label="Thread history" className="hidden w-[272px] shrink-0 flex-col border-r border-line bg-panel lg:flex">
        <div className="p-3">
          <NewThreadButton wid={workspace.id} onStart={focus} />
        </div>
        <ThreadList wid={workspace.id} now={now} />
        {admin ? (
          <div className="border-t border-line p-2">
            <Button asChild variant="ghost" className="min-h-9 w-full justify-start gap-2 px-2.5 text-fg-secondary">
              <Link href={agentSettingsHref(workspace.slug)}>
                <History aria-hidden /> Run history
              </Link>
            </Button>
          </div>
        ) : null}
      </aside>
      <section aria-label="Conversation" className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-line-subtle px-4" data-testid="ask-header">
          <Sparkles className="size-4 shrink-0 text-brand-fg" aria-hidden />
          <h1 className="min-w-0 flex-1 truncate text-base font-semibold">Ask Social Hood</h1>
          {admin ? (
            <Button asChild variant="ghost" size="icon" className="size-10 text-fg-secondary lg:hidden">
              <Link href={agentSettingsHref(workspace.slug)} aria-label="Run history">
                <History aria-hidden />
              </Link>
            </Button>
          ) : null}
          <div className="lg:hidden">
            <ThreadMenu wid={workspace.id} now={now} onPick={focus} />
          </div>
          <div className="lg:hidden">
            <NewThreadButton wid={workspace.id} iconOnly onStart={focus} />
          </div>
        </div>
        <AskConversation composerId={PAGE_COMPOSER_ID} variant="page" />
      </section>
    </div>
  );
}
