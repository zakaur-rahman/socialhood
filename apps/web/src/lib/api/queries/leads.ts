"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { ContactRecord, LeadSettings, LeadStage, LeadSummary } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/** Contacts per stage, open leads gone cold, and the last 8 weeks of qualified and won (GR-18). */
export function useLeadSummary(wid: string) {
  const api = useApi();
  return useQuery<LeadSummary, Error>({
    queryKey: keys.leadSummary(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/leads/summary", { params: { path: { wid } } })),
  });
}

/** Move a lead to a stage, with an optional note (the reason, kept in the history). Any member. */
export function useSetLeadStage(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactRecord, Error, { id: string; stage: LeadStage; note?: string }>({
    mutationFn: ({ id, stage, note }) =>
      unwrap(
        api.POST("/v1/w/{wid}/contacts/{contact_id}/lead-stage", {
          params: { path: { wid, contact_id: id } },
          body: { stage, note: note?.trim() ? note.trim() : undefined },
        }),
      ),
    onSuccess: (record) => {
      queryClient.setQueryData(keys.contact(wid, record.id), record);
      // The cards (every list and count), the drawer's timeline and the stage counts.
      void queryClient.invalidateQueries({ queryKey: keys.contactLists(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.leadSummary(wid) });
    },
  });
}

/** After how many quiet days a qualified or follow-up lead goes cold. */
export function useLeadSettings(wid: string) {
  const api = useApi();
  return useQuery<LeadSettings, Error>({
    queryKey: keys.leadSettings(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/leads/settings", { params: { path: { wid } } })),
  });
}

export function useUpdateLeadSettings(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<LeadSettings, Error, number>({
    mutationFn: (days) =>
      unwrap(api.PATCH("/v1/w/{wid}/leads/settings", { params: { path: { wid } }, body: { cold_after_days: days } })),
    onSuccess: (settings) => {
      queryClient.setQueryData(keys.leadSettings(wid), settings);
      void queryClient.invalidateQueries({ queryKey: keys.leadSummary(wid) });
    },
  });
}
