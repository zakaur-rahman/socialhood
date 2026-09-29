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
 * /w/[slug]/ask (FR-AGT-01): Ask Social Hood as a full page, with the thread history beside the
 * conversation from 1024 px (a menu below that). It shows the same thread as the panel.
 */
export function AskPage() {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const admin = workspace.role !== "agent";
  const focus = () => document.getElementById(PAGE_COMPOSER_ID)?.focus();

  return (
    <div
      className="flex h-[calc(100dvh-56px)] flex-col overflow-hidden bg-panel md:mx-4 md:mt-4 md:h-[calc(100dvh-32px)] md:rounded-xl md:border md:border-line"
      data-testid="ask-page"
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-line px-4 py-3">
        <Sparkles className="hidden size-5 shrink-0 text-brand-fg md:block" aria-hidden />
        <h1 className="min-w-0 flex-1 truncate text-xl font-semibold">Ask Social Hood</h1>
        {admin ? (
          <Button asChild variant="ghost" className="min-h-10 text-fg-secondary md:min-h-8">
            <Link href={agentSettingsHref(workspace.slug)} aria-label="Run history">
              <History aria-hidden /> <span className="hidden sm:inline">Run history</span>
            </Link>
          </Button>
        ) : null}
        <div className="lg:hidden">
          <ThreadMenu wid={workspace.id} now={now} onPick={focus} />
        </div>
        <div className="lg:hidden">
          <NewThreadButton wid={workspace.id} iconOnly onStart={focus} />
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <aside aria-label="Thread history" className="hidden w-[280px] shrink-0 flex-col border-r border-line lg:flex">
          <div className="border-b border-line p-3">
            <NewThreadButton wid={workspace.id} onStart={focus} />
          </div>
          <ThreadList wid={workspace.id} now={now} />
        </aside>
        <section aria-label="Conversation" className="flex min-w-0 flex-1 flex-col">
          <AskConversation composerId={PAGE_COMPOSER_ID} />
        </section>
      </div>
    </div>
  );
}
