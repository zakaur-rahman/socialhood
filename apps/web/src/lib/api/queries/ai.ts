"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { setLatestAnalysis, setPendingSuggestion } from "@/lib/inbox/cache";

import { useApi } from "../provider";
import type {
  AiDecision,
  AiSettings,
  AiSettingsUpdate,
  AnalysisCorrection,
  Conversation,
  MessageAnalysis,
  PolishRequest,
  PolishResult,
  Suggestion,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

// ---- AI settings (FR-KB-04 brand voice, FR-SUG-05 takeover, FR-SUG-06 escalation phrases)

/** Admins only (the API answers 403 to agents), so callers pass enabled=false for agents. */
export function useAiSettings(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<AiSettings>({
    queryKey: keys.aiSettings(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/ai-settings", { params: { path: { wid } } })),
  });
}

/** The whole object replaces the stored one (PUT), so callers start from the loaded settings. */
export function toSettingsUpdate(settings: AiSettings): AiSettingsUpdate {
  return {
    business_name: settings.business_name ?? null,
    business_description: settings.business_description ?? null,
    tone: settings.tone,
    emoji_policy: settings.emoji_policy,
    do_list: settings.do_list,
    dont_list: settings.dont_list,
    escalation_phrases: settings.escalation_phrases,
    sign_off: settings.sign_off ?? null,
    takeover_minutes: settings.takeover_minutes,
  };
}

export function useUpdateAiSettings(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AiSettings, Error, AiSettingsUpdate>({
    mutationFn: (body) => unwrap(api.PUT("/v1/w/{wid}/ai-settings", { params: { path: { wid } }, body })),
    onSuccess: (settings) => {
      queryClient.setQueryData(keys.aiSettings(wid), settings);
      void queryClient.invalidateQueries({ queryKey: ["w", wid, "overview"] });
    },
  });
}

// ---- analysis corrections (FR-AI-04)

export function useCorrectAnalysis(wid: string, conversationId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<MessageAnalysis, Error, { id: string; correction: AnalysisCorrection }>({
    mutationFn: ({ id, correction }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/message-analyses/{analysis_id}", {
          params: { path: { wid, analysis_id: id } },
          body: correction,
        }),
      ),
    onSuccess: (analysis) => setLatestAnalysis(queryClient, wid, conversationId, analysis),
  });
}

// ---- suggestions (F-08)

/** Regenerate (202): suggestion.created brings the new draft; up to 5 per message. */
export function useRegenerateSuggestion(wid: string, conversationId: string) {
  const api = useApi();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      expectOk(
        api.POST("/v1/w/{wid}/conversations/{conversation_id}/suggestions", {
          params: { path: { wid, conversation_id: conversationId } },
        }),
      ),
  });
}

/** Dismiss closes the card at once; a failure puts it back. */
export function useDismissSuggestion(wid: string, conversationId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Suggestion, Error, Suggestion, { previous: Suggestion }>({
    mutationFn: (suggestion) =>
      unwrap(
        api.POST("/v1/w/{wid}/suggestions/{suggestion_id}/dismiss", {
          params: { path: { wid, suggestion_id: suggestion.id } },
        }),
      ),
    onMutate: (suggestion) => {
      setPendingSuggestion(queryClient, wid, conversationId, null, suggestion.id);
      return { previous: suggestion };
    },
    onError: (_error, _suggestion, context) => {
      const detail = queryClient.getQueryData<Conversation>(keys.conversation(wid, conversationId));
      // Put it back unless a newer suggestion arrived meanwhile.
      if (context && detail && !detail.pending_suggestion) {
        setPendingSuggestion(queryClient, wid, conversationId, context.previous);
      }
    },
  });
}

// ---- summaries (FR-AI-03)

/** Refresh on request (202); the new summary arrives with conversation.updated. */
export function useRefreshSummary(wid: string, conversationId: string) {
  const api = useApi();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      expectOk(
        api.POST("/v1/w/{wid}/conversations/{conversation_id}/summary", {
          params: { path: { wid, conversation_id: conversationId } },
        }),
      ),
  });
}

// ---- AI Polish (C-063)

/** The composer's AI Polish: the draft back with its grammar and clarity fixed (1 credit). */
export function usePolishReply(wid: string, conversationId: string) {
  const api = useApi();
  return useMutation<PolishResult, Error, PolishRequest>({
    mutationFn: (body) =>
      unwrap(
        api.POST("/v1/w/{wid}/conversations/{conversation_id}/polish", {
          params: { path: { wid, conversation_id: conversationId } },
          body,
        }),
      ),
  });
}

// ---- auto-reply decisions (FR-SUG-04)

/** Why the AI sent (or did not send) a reply: for an AI message, the decision that sent it. */
export function useAiDecision(wid: string, messageId: string, enabled = true) {
  const api = useApi();
  return useQuery<AiDecision>({
    queryKey: keys.aiDecision(wid, messageId),
    enabled,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/messages/{message_id}/ai-decision", {
          params: { path: { wid, message_id: messageId } },
        }),
      ),
  });
}

/** "Should not have sent": feedback "bad"; null takes it back. */
export function useAiDecisionFeedback(wid: string, messageId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AiDecision, Error, { decisionId: string; feedback: "bad" | null }>({
    mutationFn: ({ decisionId, feedback }) =>
      unwrap(
        api.POST("/v1/w/{wid}/ai-decisions/{decision_id}/feedback", {
          params: { path: { wid, decision_id: decisionId } },
          body: { feedback },
        }),
      ),
    onSuccess: (decision) => queryClient.setQueryData(keys.aiDecision(wid, messageId), decision),
  });
}
