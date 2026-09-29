"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { toApiError } from "@/lib/api/errors";
import { useApi } from "@/lib/api/provider";

import { applyRealtimeEvent, invalidateWorkspace } from "./events";
import { runEventStream } from "./sse";
import { setRealtimeStatus } from "./status";

/**
 * TR-FE-04: one event stream per tab, opened by the workspace layout. Each (re)connect asks
 * the API client for a fresh token and sends the last seen id as Last-Event-ID; a reconnect
 * that cannot resume refetches the workspace's queries instead. The connection state goes to
 * lib/realtime/status for the sidebar.
 */
export function useWorkspaceEvents(wid: string, openConversationId: string | null): void {
  const api = useApi();
  const queryClient = useQueryClient();
  const openRef = useRef(openConversationId);

  useEffect(() => {
    openRef.current = openConversationId;
  }, [openConversationId]);

  useEffect(() => {
    const controller = new AbortController();
    setRealtimeStatus("connecting");
    void runEventStream({
      signal: controller.signal,
      open: async (lastEventId, signal) => {
        const { data, error, response } = await api.GET("/v1/w/{wid}/events", {
          params: { path: { wid }, ...(lastEventId ? { header: { "Last-Event-ID": lastEventId } } : {}) },
          headers: { Accept: "text/event-stream" },
          parseAs: "stream",
          cache: "no-store",
          signal,
        });
        if (!response.ok || !data) throw toApiError(error, response.status);
        return data;
      },
      onOpen: ({ reconnect, resumed }) => {
        setRealtimeStatus("connected");
        if (reconnect && !resumed) void invalidateWorkspace(queryClient, wid);
      },
      onReconnecting: () => setRealtimeStatus("reconnecting"),
      onEvent: (event) => applyRealtimeEvent(queryClient, wid, event, { openConversationId: openRef.current }),
    });
    return () => controller.abort();
  }, [api, queryClient, wid]);
}
