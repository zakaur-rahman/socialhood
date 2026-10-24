"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  ContactSequenceList,
  EnrolmentStatus,
  Sequence,
  SequenceBody,
  SequenceEnrolment,
  SequenceEnrolmentList,
  SequenceList,
  SequencePreview,
} from "../types";
import { keys } from "./keys";
import { expectOk, unwrap } from "./unwrap";

export const PEOPLE_PAGE = 25;

/** Every sequence, newest first, with its enrolment counts and the plan's limits (owners and admins). */
export function useSequences(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<SequenceList, Error>({
    queryKey: keys.sequenceList(wid),
    enabled,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/sequences", { params: { path: { wid } } })),
  });
}

/** One sequence with its steps. */
export function useSequence(wid: string, id: string) {
  const api = useApi();
  return useQuery<Sequence, Error>({
    queryKey: keys.sequence(wid, id),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/sequences/{sequence_id}", { params: { path: { wid, sequence_id: id } } })),
  });
}

/** The people in a sequence, 25 at a time, optionally one status. */
export function useSequencePeople(wid: string, id: string, status: EnrolmentStatus | null, page: number) {
  const api = useApi();
  return useQuery<SequenceEnrolmentList, Error>({
    queryKey: keys.sequencePeople(wid, id, status, page),
    placeholderData: keepPreviousData,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/sequences/{sequence_id}/enrolments", {
          params: {
            path: { wid, sequence_id: id },
            query: { status: status ?? undefined, limit: PEOPLE_PAGE, offset: page * PEOPLE_PAGE },
          },
        }),
      ),
  });
}

/** The sequences a contact is in or has been in, with what happened at each step (any member). */
export function useContactSequences(wid: string, contactId: string | null) {
  const api = useApi();
  return useQuery<ContactSequenceList, Error>({
    queryKey: keys.contactSequences(wid, contactId ?? ""),
    enabled: Boolean(contactId),
    retry: false,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/contacts/{contact_id}/sequences", {
          params: { path: { wid, contact_id: contactId ?? "" } },
        }),
      ),
  });
}

/** The editor's preview: when each step goes after entry and what it sends. Nothing is saved. */
export function useSequencePreview(wid: string, body: SequenceBody | null) {
  const api = useApi();
  return useQuery<SequencePreview, Error>({
    queryKey: keys.sequencePreview(wid, body),
    enabled: body !== null,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    retry: false,
    queryFn: () =>
      unwrap(api.POST("/v1/w/{wid}/sequences/preview", { params: { path: { wid } }, body: body as SequenceBody })),
  });
}

function refresh(queryClient: ReturnType<typeof useQueryClient>, wid: string) {
  void queryClient.invalidateQueries({ queryKey: keys.sequences(wid) });
}

export function useCreateSequence(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Sequence, Error, SequenceBody>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/sequences", { params: { path: { wid } }, body })),
    onSuccess: () => refresh(queryClient, wid),
  });
}

export function useUpdateSequence(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Sequence, Error, { id: string; body: SequenceBody }>({
    mutationFn: ({ id, body }) =>
      unwrap(api.PUT("/v1/w/{wid}/sequences/{sequence_id}", { params: { path: { wid, sequence_id: id } }, body })),
    onSuccess: () => refresh(queryClient, wid),
  });
}

export function useSequenceAction(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<Sequence, Error, { id: string; action: "activate" | "pause" }>({
    mutationFn: ({ id, action }) => {
      const params = { params: { path: { wid, sequence_id: id } } };
      return action === "activate"
        ? unwrap(api.POST("/v1/w/{wid}/sequences/{sequence_id}/activate", params))
        : unwrap(api.POST("/v1/w/{wid}/sequences/{sequence_id}/pause", params));
    },
    onSuccess: () => refresh(queryClient, wid),
  });
}

export function useDeleteSequence(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/sequences/{sequence_id}", { params: { path: { wid, sequence_id: id } } })),
    onSuccess: () => refresh(queryClient, wid),
  });
}

/** Take one person out of a sequence. */
export function useStopEnrolment(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<SequenceEnrolment, Error, { sequenceId: string; enrolmentId: string }>({
    mutationFn: ({ sequenceId, enrolmentId }) =>
      unwrap(
        api.POST("/v1/w/{wid}/sequences/{sequence_id}/enrolments/{enrolment_id}/stop", {
          params: { path: { wid, sequence_id: sequenceId, enrolment_id: enrolmentId } },
        }),
      ),
    onSuccess: () => refresh(queryClient, wid),
  });
}
