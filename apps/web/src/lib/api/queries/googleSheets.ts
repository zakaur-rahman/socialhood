"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { GoogleSheetColumn, GoogleSheetsStatus, GoogleSheetTestResult } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** While rows are waiting for Google, the card refreshes this often. */
export const SHEETS_POLL_MS = 5_000;

/** The workspace's Google Sheets sync (GR-27): connection, sheet, columns and the latest rows. */
export function useGoogleSheets(wid: string) {
  const api = useApi();
  return useQuery<GoogleSheetsStatus>({
    queryKey: keys.googleSheets(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/integrations/google-sheets", { params: { path: { wid } } })),
    refetchInterval: (query) => ((query.state.data?.pending_rows ?? 0) > 0 ? SHEETS_POLL_MS : false),
  });
}

function useStatusMutation<TVars>(wid: string, call: (vars: TVars) => Promise<GoogleSheetsStatus>) {
  const queryClient = useQueryClient();
  return useMutation<GoogleSheetsStatus, Error, TVars>({
    mutationFn: call,
    onSuccess: (status) => queryClient.setQueryData(keys.googleSheets(wid), status),
  });
}

/** Google's authorize URL; the caller navigates there. 402 without Sheets sync on the plan. */
export function useStartGoogleConnect(wid: string) {
  const api = useApi();
  return useMutation<string, Error, void>({
    mutationFn: async () =>
      (await unwrap(api.POST("/v1/w/{wid}/integrations/google-sheets/connect", { params: { path: { wid } } })))
        .authorize_url,
  });
}

/**
 * The OAuth callback sends the browser back with ?google=<nonce>; this finishes the connect as the
 * signed-in member. Only the member who started it can (403 otherwise), once and within 10 minutes.
 */
export function useCompleteGoogleConnect(wid: string) {
  const api = useApi();
  return useStatusMutation<string>(wid, (nonce) =>
    unwrap(
      api.POST("/v1/w/{wid}/integrations/google-sheets/complete", { params: { path: { wid } }, body: { nonce } }),
    ),
  );
}

export function useCreateGoogleSheet(wid: string) {
  const api = useApi();
  return useStatusMutation<string>(wid, (title) =>
    unwrap(api.POST("/v1/w/{wid}/integrations/google-sheets/sheet", { params: { path: { wid } }, body: { title } })),
  );
}

export function useSelectGoogleSheet(wid: string) {
  const api = useApi();
  return useStatusMutation<string>(wid, (link) =>
    unwrap(api.PUT("/v1/w/{wid}/integrations/google-sheets/sheet", { params: { path: { wid } }, body: { link } })),
  );
}

export function useSaveSheetMapping(wid: string) {
  const api = useApi();
  return useStatusMutation<GoogleSheetColumn[]>(wid, (columns) =>
    unwrap(
      api.PUT("/v1/w/{wid}/integrations/google-sheets/mapping", { params: { path: { wid } }, body: { columns } }),
    ),
  );
}

export function useSendSheetTest(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<GoogleSheetTestResult, Error, void>({
    mutationFn: () => unwrap(api.POST("/v1/w/{wid}/integrations/google-sheets/test", { params: { path: { wid } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.googleSheets(wid) }),
  });
}

export function useDisconnectGoogleSheets(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () =>
      expectOk(api.DELETE("/v1/w/{wid}/integrations/google-sheets", { params: { path: { wid } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.googleSheets(wid) }),
  });
}
