"use client";

import { cn } from "@/lib/utils";
import { PANE_TITLE } from "@/styles/tokens";
import { History, ListChecks, Sparkles } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { Button } from "@/components/ui/button";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { agentSettingsHref } from "@/lib/agent/routes";
import { useNow } from "@/lib/use-browser-state";
import { usePaneWidth, type PaneWidthLimits } from "@/lib/use-pane-width";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AskConversation } from "./AskConversation";
import { PAGE_COMPOSER_ID } from "./AskPanel";
import { NewThreadButton, ThreadList, ThreadMenu } from "./Threads";

/**
 * /w/[slug]/ask (FR-AGT-01): Ask Social Hood as a full page. Thread history on the left from
 * 1024 px (a menu below that); the conversation and the question box in one centred, readable
 * column. It shows the same thread as the panel.
 */
/** The thread history column is resizable (UI-078), remembered per device. */
const THREADS_LIMITS: PaneWidthLimits = { fallback: 272, min: 220, max: 440 };

export function AskPage() {
  const workspace = useCurrentWorkspace();
  const now = useNow();
  const [threadsWidth, setThreadsWidth, resetThreadsWidth] = usePaneWidth("ask-threads", THREADS_LIMITS);
  const admin = workspace.role !== "agent";
  const focus = () => document.getElementById(PAGE_COMPOSER_ID)?.focus();

  return (
    // Fills what <main> has left under any banner (data-shell-fill, AppShell's ShellFrame).
    <div
      className="flex min-h-0 flex-1 overflow-hidden bg-canvas md:m-4 md:rounded-xl md:border md:border-line"
      data-testid="ask-page"
      data-shell-fill
    >
      <aside
        aria-label="Thread history"
        className="relative hidden w-(--pane-w) max-w-[40%] shrink-0 flex-col border-r border-line glass-pane lg:flex"
        style={{ "--pane-w": `${threadsWidth}px` } as CSSProperties}
      >
        <ResizeHandle
          edge="end"
          label="Resize the thread history"
          value={threadsWidth}
          min={THREADS_LIMITS.min}
          max={THREADS_LIMITS.max}
          onChange={setThreadsWidth}
          onReset={resetThreadsWidth}
        />
        <div className="p-3">
          <NewThreadButton wid={workspace.id} onStart={focus} />
        </div>
        <ThreadList wid={workspace.id} now={now} />
        {admin ? (
          <div className="border-t border-line p-2">
            <Button asChild variant="ghost" size="lg" className="w-full justify-start gap-2 px-2.5 text-fg-secondary">
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
          <h1 className={cn("min-w-0 flex-1 truncate", PANE_TITLE)}>Ask Social Hood</h1>
          {admin ? (
            <Button asChild variant="ghost" size="icon" className="text-fg-secondary lg:hidden">
              <Link href={agentSettingsHref(workspace.slug)} aria-label="Run history">
                <ListChecks aria-hidden />
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
