"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { WidgetSettings, WidgetSettingsUpdate } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/**
 * GR-28: the website chat widget's settings and embed code. The first read by an owner or admin
 * makes the widget (one per workspace), so an agent never calls it (the tab is hidden for them).
 */
export function useWidgetSettings(wid: string) {
  const api = useApi();
  return useQuery<WidgetSettings>({
    queryKey: keys.widget(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/widget", { params: { path: { wid } } })),
  });
}

/** Change the settings sent; the answer is all of them. */
export function useSaveWidgetSettings(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<WidgetSettings, Error, WidgetSettingsUpdate>({
    mutationFn: (body) => unwrap(api.PUT("/v1/w/{wid}/widget", { params: { path: { wid } }, body })),
    onSuccess: (data) => queryClient.setQueryData(keys.widget(wid), data),
  });
}
