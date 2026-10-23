"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { compile, decompile, makeStep, stepIds, type EditorStep, type StepKind } from "@/lib/automations/flow";

import { useApi } from "../provider";
import type { Flow, FlowDefinition, FlowFieldDefinition, FlowTag } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/**
 * GR-13: an automation's flow. ``source: legacy`` is the flow compiled from its message settings
 * (version 0, nothing stored); ``flow`` was saved with the editor.
 */
export function useAutomationFlow(wid: string, id: string, enabled = true) {
  const api = useApi();
  return useQuery<Flow>({
    queryKey: keys.automationFlow(wid, id),
    enabled,
    staleTime: 0,
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/automations/{automation_id}/flow", { params: { path: { wid, automation_id: id } } })),
  });
}

/** Refresh the automation after its flow changed: its action, status and what's missing follow it. */
function useRefreshAutomation(wid: string, id: string) {
  const queryClient = useQueryClient();
  return (flow: Flow) => {
    queryClient.setQueryData(keys.automationFlow(wid, id), flow);
    void queryClient.invalidateQueries({ queryKey: keys.automation(wid, id) });
    void queryClient.invalidateQueries({ queryKey: keys.automationLists(wid) });
  };
}

/** The autosave PUT of a flow; a 402 is the plan's step cap, a 422 names the steps. */
export function useSaveFlow(wid: string, id: string) {
  const api = useApi();
  const refresh = useRefreshAutomation(wid, id);
  return useMutation<Flow, Error, FlowDefinition>({
    mutationFn: (body) =>
      unwrap(
        api.PUT("/v1/w/{wid}/automations/{automation_id}/flow", {
          params: { path: { wid, automation_id: id } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

/**
 * An automation on its message settings gets its first extra step (GR-13): its flow compiled from
 * the settings is read, the new step goes at the end, and the whole thing is saved as a flow. The
 * settings stay where they are, so "Back to one message" returns to them.
 */
export function useStartFlow(wid: string, id: string) {
  const api = useApi();
  const refresh = useRefreshAutomation(wid, id);
  return useMutation<{ flow: Flow; tree: EditorStep[] }, Error, StepKind>({
    mutationFn: async (kind) => {
      const compiled = await unwrap(
        api.GET("/v1/w/{wid}/automations/{automation_id}/flow", { params: { path: { wid, automation_id: id } } }),
      );
      const tree = decompile(compiled.definition);
      if (!tree) throw new Error("The message can't be turned into steps.");
      const next = [...tree, makeStep(kind, stepIds(tree))];
      const flow = await unwrap(
        api.PUT("/v1/w/{wid}/automations/{automation_id}/flow", {
          params: { path: { wid, automation_id: id } },
          body: compile(next).definition,
        }),
      );
      return { flow, tree: next };
    },
    onSuccess: ({ flow }) => refresh(flow),
  });
}

/** Back to the automation's message settings (a single message). */
export function useResetFlow(wid: string, id: string) {
  const api = useApi();
  const refresh = useRefreshAutomation(wid, id);
  return useMutation<Flow, Error, void>({
    mutationFn: () =>
      unwrap(
        api.DELETE("/v1/w/{wid}/automations/{automation_id}/flow", { params: { path: { wid, automation_id: id } } }),
      ),
    onSuccess: refresh,
  });
}

/** The workspace's tags, for the steps that tag or branch on them. */
export function useFlowTags(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<FlowTag[]>({
    queryKey: keys.flowTags(wid),
    enabled,
    staleTime: 60_000,
    queryFn: async () => (await unwrap(api.GET("/v1/w/{wid}/tags", { params: { path: { wid } } }))).items,
  });
}

/** The workspace's custom contact fields, for the steps that save to or branch on them. */
export function useFlowFields(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<FlowFieldDefinition[]>({
    queryKey: keys.flowFields(wid),
    enabled,
    staleTime: 60_000,
    queryFn: async () => (await unwrap(api.GET("/v1/w/{wid}/contact-fields", { params: { path: { wid } } }))).items,
  });
}

