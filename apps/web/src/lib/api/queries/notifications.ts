"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { NotificationPreferences, PushConfig, PushDevice, PushSubscriptionCreate } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** FR-NOT-03, FR-NOT-04 (C-049): the member's weekly digest switch and four push switches. */
export function useNotificationPreferences(wid: string) {
  const api = useApi();
  return useQuery<NotificationPreferences>({
    queryKey: keys.notificationPreferences(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/notification-preferences", { params: { path: { wid } } })),
  });
}

/**
 * PUT sends the whole object (C-049). The switch moves at once and goes back if the API refuses;
 * the answer replaces the cache.
 */
export function useUpdateNotificationPreferences(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  const key = keys.notificationPreferences(wid);
  return useMutation<
    NotificationPreferences,
    Error,
    NotificationPreferences,
    { previous: NotificationPreferences | undefined }
  >({
    mutationFn: (prefs) =>
      unwrap(api.PUT("/v1/w/{wid}/notification-preferences", { params: { path: { wid } }, body: prefs })),
    onMutate: async (prefs) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<NotificationPreferences>(key);
      queryClient.setQueryData(key, prefs);
      return { previous };
    },
    onError: (_error, _prefs, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (saved) => queryClient.setQueryData(key, saved),
  });
}

/** TR-FE-09, C-049: the VAPID public key; enabled is false when the API has none. */
export function usePushConfig(enabled = true) {
  const api = useApi();
  return useQuery<PushConfig>({
    queryKey: keys.pushConfig,
    enabled,
    staleTime: Infinity,
    queryFn: () => unwrap(api.GET("/v1/push/config")),
  });
}

/** F-19: register this browser's subscription (again, to refresh it or move it to this user). */
export function useRegisterPush() {
  const api = useApi();
  return useMutation<PushDevice, Error, PushSubscriptionCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/me/push-subscriptions", { body })),
  });
}

/** Push turned off on this device: 204 whether or not the endpoint was known (C-049). */
export function useUnregisterPush() {
  const api = useApi();
  return useMutation<void, Error, string>({
    mutationFn: (endpoint) => expectOk(api.DELETE("/v1/me/push-subscriptions", { params: { query: { endpoint } } })),
  });
}
