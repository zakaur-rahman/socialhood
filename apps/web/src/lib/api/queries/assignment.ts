"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applyConversation } from "@/lib/inbox/cache";

import { useApi } from "../provider";
import type { AssignmentOverview, Conversation } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** GR-20: who can be given a conversation (any member reads it), and whether round-robin is on. */
export function useAssignment(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<AssignmentOverview>({
    queryKey: keys.assignment(wid),
    enabled,
    staleTime: 30_000,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/assignment", { params: { path: { wid } } })),
  });
}

/** Give a conversation to a member, or to nobody (`userId` null). Every list and the detail follow. */
export function useAssignConversation(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Conversation, Error, { id: string; userId: string | null }>({
    mutationFn: ({ id, userId }) =>
      unwrap(
        api.PUT("/v1/w/{wid}/conversations/{conversation_id}/assignee", {
          params: { path: { wid, conversation_id: id } },
          body: { user_id: userId },
        }),
      ),
    onSuccess: (conversation) => {
      queryClient.setQueryData(keys.conversation(wid, conversation.id), conversation);
      applyConversation(queryClient, wid, conversation);
      // "Assigned to me" is decided by the server: refetch the lists, the counts and who has how many.
      void queryClient.invalidateQueries({ queryKey: keys.conversationLists(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.inboxCounts(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.assignment(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.contactLists(wid) });
    },
  });
}

/** Turn round-robin on or off for the workspace (owners and admins). */
export function useSetRoundRobin(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<AssignmentOverview, Error, boolean>({
    mutationFn: (roundRobin) =>
      unwrap(
        api.PUT("/v1/w/{wid}/assignment/settings", {
          params: { path: { wid } },
          body: { round_robin: roundRobin },
        }),
      ),
    onSuccess: (overview) => queryClient.setQueryData(keys.assignment(wid), overview),
  });
}

/** Whether round-robin may hand a member new conversations: your own, or anyone's as an admin. */
export function useSetAvailability(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, { userId: string; available: boolean }>({
    mutationFn: ({ userId, available }) =>
      expectOk(
        api.PUT("/v1/w/{wid}/members/{user_id}/availability", {
          params: { path: { wid, user_id: userId } },
          body: { available },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.assignment(wid) }),
  });
}
