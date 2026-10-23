"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { filtersToQuery, type ContactFilters } from "@/lib/contacts/filters";

import { useApi } from "../provider";
import type {
  BulkTagsResult,
  BulkTagsUpdate,
  ConsentCreate,
  ContactCount,
  ContactList,
  ContactPatch,
  ContactRecord,
  ContactSegment,
  ContactSegmentCreate,
  ContactSegmentList,
  ContactSegmentPatch,
  ContactTag,
  FieldDefinitionList,
  TagCreate,
  TagList,
  TimelineList,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

const PAGE = 50;
const TIMELINE_PAGE = 20;

export type ContactPages = { pages: ContactList[]; pageParams: (string | null)[] };
export type TimelinePages = { pages: TimelineList[]; pageParams: (string | null)[] };

/** The contacts page (GR-17): filtered on the server, newest activity first, in cursor pages. */
export function useContacts(wid: string, filters: ContactFilters) {
  const api = useApi();
  return useInfiniteQuery<ContactList, Error, ContactPages, ReturnType<typeof keys.contacts>, string | null>({
    queryKey: keys.contacts(wid, filters),
    initialPageParam: null,
    // A new filter keeps the rows on screen until its results arrive.
    placeholderData: (previous) => previous,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/contacts", {
          params: { path: { wid }, query: { ...filtersToQuery(filters), cursor: pageParam ?? undefined, limit: PAGE } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

/** How many contacts match, for "Select all 312" and the bulk cap. */
export function useContactCount(wid: string, filters: ContactFilters, enabled = true) {
  const api = useApi();
  return useQuery<ContactCount, Error, number>({
    queryKey: keys.contactCount(wid, filters),
    enabled,
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/contacts/count", { params: { path: { wid }, query: filtersToQuery(filters) } })),
    select: (result) => result.count,
  });
}

export function useContact(wid: string, id: string | null) {
  const api = useApi();
  return useQuery<ContactRecord, Error>({
    queryKey: keys.contact(wid, id ?? ""),
    enabled: id !== null,
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/contacts/{contact_id}", { params: { path: { wid, contact_id: id ?? "" } } })),
  });
}

/** A contact's timeline (conversations, comments, runs, mentions, consent, tags), read-only. */
export function useContactTimeline(wid: string, id: string | null) {
  const api = useApi();
  return useInfiniteQuery<TimelineList, Error, TimelinePages, ReturnType<typeof keys.contactTimeline>, string | null>({
    queryKey: keys.contactTimeline(wid, id ?? ""),
    enabled: id !== null,
    initialPageParam: null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/v1/w/{wid}/contacts/{contact_id}/timeline", {
          params: {
            path: { wid, contact_id: id ?? "" },
            query: { cursor: pageParam ?? undefined, limit: TIMELINE_PAGE },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
}

export function useTags(wid: string) {
  const api = useApi();
  return useQuery<TagList, Error, ContactTag[]>({
    queryKey: keys.tags(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/tags", { params: { path: { wid } } })),
    select: (list) => list.items,
  });
}

export function useCreateTag(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactTag, Error, TagCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/tags", { params: { path: { wid } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.tags(wid) }),
  });
}

/** The workspace's custom field definitions, in order, with the plan's limit. */
export function useContactFields(wid: string) {
  const api = useApi();
  return useQuery<FieldDefinitionList, Error>({
    queryKey: keys.contactFields(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/contact-fields", { params: { path: { wid } } })),
  });
}

/** Edit a contact's email, phone and fields. */
export function useUpdateContact(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactRecord, Error, { id: string; body: ContactPatch }>({
    mutationFn: ({ id, body }) =>
      unwrap(api.PATCH("/v1/w/{wid}/contacts/{contact_id}", { params: { path: { wid, contact_id: id } }, body })),
    onSuccess: (record) => {
      queryClient.setQueryData(keys.contact(wid, record.id), record);
      void queryClient.invalidateQueries({ queryKey: keys.contactLists(wid) });
    },
  });
}

/** Add and remove tags on one contact. */
export function useTagContact(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactRecord, Error, { id: string; add?: string[]; remove?: string[] }>({
    mutationFn: ({ id, add, remove }) =>
      unwrap(
        api.POST("/v1/w/{wid}/contacts/{contact_id}/tags", {
          params: { path: { wid, contact_id: id } },
          body: { add: add ?? [], remove: remove ?? [] },
        }),
      ),
    onSuccess: (record) => {
      queryClient.setQueryData(keys.contact(wid, record.id), record);
      void queryClient.invalidateQueries({ queryKey: keys.contactLists(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.tags(wid) });
    },
  });
}

/** Record consent given elsewhere, or its withdrawal (admins). */
export function useRecordConsent(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactRecord, Error, { id: string; body: ConsentCreate }>({
    mutationFn: ({ id, body }) =>
      unwrap(
        api.POST("/v1/w/{wid}/contacts/{contact_id}/consents", { params: { path: { wid, contact_id: id } }, body }),
      ),
    onSuccess: (record) => {
      queryClient.setQueryData(keys.contact(wid, record.id), record);
      void queryClient.invalidateQueries({ queryKey: keys.contactLists(wid) });
    },
  });
}

/** Tag the chosen contacts, or everyone a filter matches. */
export function useBulkTag(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<BulkTagsResult, Error, BulkTagsUpdate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/contacts/bulk-tags", { params: { path: { wid } }, body })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.contactLists(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.tags(wid) });
    },
  });
}

export function useContactSegments(wid: string) {
  const api = useApi();
  return useQuery<ContactSegmentList, Error, ContactSegment[]>({
    queryKey: keys.contactSegments(wid),
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/contact-segments", { params: { path: { wid } } })),
    select: (list) => list.items,
  });
}

export function useCreateSegment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactSegment, Error, ContactSegmentCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/contact-segments", { params: { path: { wid } }, body })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.contactSegments(wid) }),
  });
}

export function useUpdateSegment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<ContactSegment, Error, { id: string; body: ContactSegmentPatch }>({
    mutationFn: ({ id, body }) =>
      unwrap(
        api.PATCH("/v1/w/{wid}/contact-segments/{segment_id}", { params: { path: { wid, segment_id: id } }, body }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.contactSegments(wid) }),
  });
}

export function useDeleteSegment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/contact-segments/{segment_id}", { params: { path: { wid, segment_id: id } } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.contactSegments(wid) }),
  });
}

/** The filtered contacts as a CSV blob (admins). The request carries the sign-in, so the file
 * cannot be a plain link. */
export function useExportContacts(wid: string) {
  const api = useApi();
  return useMutation<Blob, Error, ContactFilters>({
    mutationFn: async (filters) => {
      const { data, error } = await api.GET("/v1/w/{wid}/contacts/export.csv", {
        params: { path: { wid }, query: filtersToQuery(filters) },
        parseAs: "blob",
      });
      if (error !== undefined || data === undefined) throw new Error("The export did not download. Try again.");
      return data as Blob;
    },
  });
}
