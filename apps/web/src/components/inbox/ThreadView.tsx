"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import type { Route } from "next";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { AiModeMenu } from "@/components/ai/AiModeControl";
import { AnalysisChips } from "@/components/ai/AnalysisChips";
import { DecisionInfo } from "@/components/ai/DecisionInfo";
import { useSuggestionSlot } from "@/components/ai/SuggestionSlot";
import type { KnowledgeUploader } from "@/components/knowledge/SourceSheet";
import { ErrorState } from "@/components/states/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import {
  isLocalMessage,
  useConversation,
  useConversationScheduled,
  useMarkRead,
  useMessages,
  useSendReply,
  useSocialAccounts,
  type ReplyInput,
} from "@/lib/api/queries";
import type { Conversation, Message } from "@/lib/api/types";
import { sendFailure, type SendFailure } from "@/lib/copy";
import { flattenMessages, setPendingSuggestion } from "@/lib/inbox/cache";
import { contactName } from "@/lib/inbox/format";
import { useInboxStore } from "@/lib/inbox/store";
import { formatDayTime } from "@/lib/tz";
import { useNow } from "@/lib/use-browser-state";
import { useCurrentWorkspace } from "@/lib/workspace";

import { Composer, type Uploader } from "./Composer";
import { useOptionalInboxUi } from "./inbox-context";
import { MessageBubble } from "./MessageBubble";
import { MessageLog } from "./MessageLog";
import { TemplatePicker } from "./TemplatePicker";
import { ThreadHeader } from "./ThreadHeader";

/** Marks the conversation read after 1 s of visibility (F-06 step 11); at once when opened. */
const READ_DELAY_MS = 1_000;

function useDocumentVisible(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      document.addEventListener("visibilitychange", onChange);
      return () => document.removeEventListener("visibilitychange", onChange);
    },
    () => document.visibilityState !== "hidden",
    () => true,
  );
}

function compareOldestFirst(a: Message, b: Message): number {
  return new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime();
}

/**
 * One conversation (UX-INB-05…07). The page renders it with key={conversationId}; drafts and
 * unsent replies come from the store by conversation id, so nothing from the previous
 * conversation can show (TR-FE-06, FR-INB-02).
 */
export function ThreadView({
  conversationId,
  upload,
  knowledgeUpload,
}: {
  conversationId: string;
  upload?: Uploader;
  /** Tests inject a fake for "Add to knowledge" file sources. */
  knowledgeUpload?: KnowledgeUploader;
}) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const conversation = useConversation(wid, conversationId);

  if (conversation.isError) {
    return <ErrorState error={conversation.error} onRetry={() => void conversation.refetch()} />;
  }
  if (!conversation.data) {
    return (
      <div className="flex h-full flex-col" aria-busy="true" aria-label="Loading conversation">
        <div className="flex h-14 items-center gap-3 border-b border-line bg-panel px-4">
          <Skeleton className="size-8 rounded-full bg-raised" />
          <Skeleton className="h-3 w-40 bg-raised" />
        </div>
        <div className="flex-1" />
      </div>
    );
  }
  return <Thread conversation={conversation.data} upload={upload} knowledgeUpload={knowledgeUpload} />;
}

function Thread({
  conversation,
  upload,
  knowledgeUpload,
}: {
  conversation: Conversation;
  upload?: Uploader;
  knowledgeUpload?: KnowledgeUploader;
}) {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const conversationId = conversation.id;
  const ui = useOptionalInboxUi();
  const now = useNow();
  const messages = useMessages(wid, conversationId);
  const accounts = useSocialAccounts(wid);
  const outbox = useInboxStore((state) => state.outbox);
  const queryClient = useQueryClient();
  const { send: sendReply, retry, discard } = useSendReply(wid, conversationId);
  const pendingSuggestionId = conversation.pending_suggestion?.id ?? null;
  // Any reply retires the pending suggestion: sent as is, edited, or typed instead (F-08).
  const send = useCallback(
    (input: ReplyInput) => {
      sendReply(input);
      if (pendingSuggestionId) setPendingSuggestion(queryClient, wid, conversationId, null, pendingSuggestionId);
    },
    [sendReply, pendingSuggestionId, queryClient, wid, conversationId],
  );
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [templateOpen, setTemplateOpen] = useState(false);

  // Server messages, plus replies still in the outbox (optimistic or failed before reaching the API).
  const all = useMemo(() => {
    const server = flattenMessages(messages.data);
    const confirmed = new Set(server.map((m) => m.client_id).filter(Boolean));
    const local = Object.values(outbox)
      .filter((entry) => entry.conversationId === conversationId && !confirmed.has(entry.clientId))
      .map((entry) => entry.message);
    return local.length ? [...server, ...local].sort(compareOldestFirst) : server;
  }, [messages.data, outbox, conversationId]);

  // The API's value covers history not loaded yet; the loaded messages fill in until it arrives.
  const lastInboundAt = useMemo(() => {
    if (conversation.last_inbound_at) return conversation.last_inbound_at;
    for (let i = all.length - 1; i >= 0; i--) if (all[i].direction === "inbound") return all[i].occurred_at;
    return null;
  }, [all, conversation.last_inbound_at]);

  // Messages that arrive after the thread opened animate in; history does not (§4.2 motion).
  const [openedAt] = useState(() => Date.now());

  useAutoRead(wid, conversation, ui?.manualUnreadId === conversationId);

  const name = contactName(conversation.contact, conversation.platform);
  const account = accounts.data?.find((a) => a.id === conversation.social_account_id);
  const canAttach = account ? account.capabilities.includes("dm_attachments") : true;
  const sameplatformAccounts = (accounts.data ?? []).filter(
    (a) => a.platform === conversation.platform && a.status !== "disconnected",
  ).length;
  const handle =
    conversation.platform === "instagram"
      ? conversation.social_account.username
      : (conversation.social_account.display_name ?? account?.phone_number);
  const reconnectHref = `/w/${workspace.slug}/settings/connections` as Route;
  const canSchedule = conversation.reply_window.state === "open" || conversation.reply_window.state === "human_agent";
  const accountStatus = conversation.social_account.status;
  // As the composer decides: replies need an open window and a connected account.
  const canReply = canSchedule && accountStatus !== "needs_reconnect" && accountStatus !== "disconnected";
  const suggestionUi = useSuggestionSlot({ conversation, messages: all, canReply, onSend: send, upload: knowledgeUpload });
  const analysis = conversation.latest_analysis ?? null;

  const failureFor = useCallback(
    (message: Message): SendFailure | null => {
      if (message.status !== "failed") return null;
      if (!message.error) return { message: "This message wasn't sent.", retry: true };
      const local = isLocalMessage(message);
      return sendFailure(
        {
          code: message.error.code,
          message: local && message.error.code === "internal" ? null : message.error.message,
          requestId: local && message.error.code === "internal" ? message.error.message : null,
        },
        { platform: conversation.platform, handle },
      );
    },
    [conversation.platform, handle],
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ThreadHeader
        conversation={conversation}
        now={now}
        backHref={ui?.layout === "phone" ? (`/w/${workspace.slug}/inbox` as Route) : undefined}
        showAccount={sameplatformAccounts > 1}
        detailsOpen={ui?.detailsOpen ?? false}
        onToggleDetails={() => ui?.toggleDetails()}
        canSchedule={canSchedule}
        onSchedule={() => setScheduleOpen(true)}
        onArchive={(archived) => ui?.archive(conversationId, archived)}
        onMarkUnread={() => ui?.markUnread(conversationId)}
        aiControl={<AiModeMenu conversation={conversation} now={now} />}
      />
      <MessageLog
        messages={all}
        timeZone={workspace.timezone}
        now={now}
        label={`Messages with ${name}`}
        loading={messages.isPending}
        hasOlder={messages.hasNextPage}
        loadingOlder={messages.isFetchingNextPage}
        loadOlder={() => void messages.fetchNextPage()}
        renderMessage={(message, row) => (
          <MessageBubble
            message={message}
            platform={conversation.platform}
            timeZone={workspace.timezone}
            contact={{ id: conversation.contact.id, name, pictureUrl: conversation.contact.profile_picture_url }}
            groupEnd={row.groupEnd}
            live={new Date(message.occurred_at).getTime() > openedAt}
            failure={failureFor(message)}
            onRetry={() => void retry(message)}
            onDiscard={isLocalMessage(message) ? () => discard(message) : undefined}
            onChooseTemplate={() => setTemplateOpen(true)}
            reconnectHref={reconnectHref}
            aiInfo={message.source === "ai_auto" && !isLocalMessage(message) ? <DecisionInfo messageId={message.id} /> : undefined}
            below={
              analysis && message.id === analysis.message_id && message.direction === "inbound" ? (
                <AnalysisChips analysis={analysis} conversationId={conversationId} />
              ) : undefined
            }
          />
        )}
      />
      {messages.isError ? (
        <div className="shrink-0 border-t border-line">
          <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />
        </div>
      ) : null}
      <ScheduledChip conversation={conversation} now={now} onOpen={() => ui?.setTab("scheduled")} />
      <div className="shrink-0 bg-canvas">{suggestionUi.slot}</div>
      <Composer
        suggestionKeys={suggestionUi.keys}
        wid={wid}
        slug={workspace.slug}
        timeZone={workspace.timezone}
        conversation={conversation}
        lastInboundAt={lastInboundAt}
        now={now}
        onSend={send}
        scheduleOpen={scheduleOpen}
        onScheduleOpenChange={setScheduleOpen}
        onChooseTemplate={() => setTemplateOpen(true)}
        canAttach={canAttach}
        upload={upload}
      />
      {conversation.platform === "whatsapp" ? (
        <TemplatePicker
          wid={wid}
          accountId={conversation.social_account_id}
          open={templateOpen}
          onOpenChange={setTemplateOpen}
          onSend={(template) => send({ template })}
        />
      ) : null}
    </div>
  );
}

/** FR-INB-04: opening marks read; later inbound messages are marked read after 1 s visible. */
function useAutoRead(wid: string, conversation: Conversation, suppressed: boolean) {
  const { mutate: markRead } = useMarkRead(wid);
  const visible = useDocumentVisible();
  const opened = useRef(false);
  const unread = conversation.unread_count;
  const id = conversation.id;

  useEffect(() => {
    if (!visible || unread === 0 || suppressed) return;
    const delay = opened.current ? READ_DELAY_MS : 0;
    const timer = window.setTimeout(() => markRead(id), delay);
    return () => window.clearTimeout(timer);
  }, [visible, unread, suppressed, id, markRead]);

  useEffect(() => {
    opened.current = true;
  }, []);
}

/** F-10: "1 scheduled · Today 18:30" above the composer; opens the Scheduled tab. */
function ScheduledChip({ conversation, now, onOpen }: { conversation: Conversation; now: Date; onOpen: () => void }) {
  const workspace = useCurrentWorkspace();
  const count = conversation.scheduled_count;
  const scheduled = useConversationScheduled(workspace.id, conversation.id, count > 0);
  if (count <= 0) return null;
  const next = scheduled.data?.items
    .filter((s) => s.status === "scheduled")
    .sort((a, b) => new Date(a.send_at).getTime() - new Date(b.send_at).getTime())[0];
  return (
    <div className="shrink-0 bg-canvas px-4 pb-2">
      <button
        type="button"
        onClick={onOpen}
        className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand-fg"
      >
        <CalendarClock className="size-3.5" aria-hidden />
        {count} scheduled{next ? ` · ${formatDayTime(next.send_at, workspace.timezone, now)}` : ""}
      </button>
    </div>
  );
}
