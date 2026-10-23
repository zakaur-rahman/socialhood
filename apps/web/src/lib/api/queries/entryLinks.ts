"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { EntryLink, EntryLinkCreate, EntryLinkList, EntryLinkUpdate, QrFormat } from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

/** GR-08: the workspace's entry links, newest first, with the conversations and runs each led to. */
export function useEntryLinks(wid: string) {
  const api = useApi();
  return useQuery<EntryLinkList, Error, EntryLink[]>({
    queryKey: keys.entryLinks(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/entry-links", { params: { path: { wid } } })),
    select: (list) => list.items,
  });
}

export function useCreateEntryLink(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<EntryLink, Error, EntryLinkCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/entry-links", { params: { path: { wid } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.entryLinks(wid) }),
  });
}

export function useUpdateEntryLink(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<EntryLink, Error, { id: string; body: EntryLinkUpdate }>({
    mutationFn: ({ id, body }) =>
      unwrap(api.PUT("/v1/w/{wid}/entry-links/{link_id}", { params: { path: { wid, link_id: id } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.entryLinks(wid) }),
  });
}

export function useDeleteEntryLink(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/entry-links/{link_id}", { params: { path: { wid, link_id: id } } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.entryLinks(wid) }),
  });
}

type Api = ReturnType<typeof useApi>;

async function fetchQr(api: Api, wid: string, id: string, format: QrFormat): Promise<Blob> {
  const { data, error } = await api.GET("/v1/w/{wid}/entry-links/{link_id}/qr", {
    params: { path: { wid, link_id: id }, query: { format } },
    parseAs: "blob",
  });
  if (error !== undefined || data === undefined) throw new Error("The QR code didn't load. Try again.");
  return data as Blob;
}

/** The link's QR code as an image blob, for the preview (the request carries the sign-in, so it
 * can't be a plain image address). */
export function useEntryLinkQr(wid: string, id: string, enabled: boolean) {
  const api = useApi();
  return useQuery<Blob, Error>({
    queryKey: [...keys.entryLinks(wid), id, "qr"],
    enabled,
    staleTime: Infinity,
    queryFn: () => fetchQr(api, wid, id, "svg"),
  });
}

/** Download a link's QR code as SVG or PNG. */
export function useDownloadEntryLinkQr(wid: string) {
  const api = useApi();
  return useMutation<Blob, Error, { id: string; format: QrFormat }>({
    mutationFn: ({ id, format }) => fetchQr(api, wid, id, format),
  });
}
