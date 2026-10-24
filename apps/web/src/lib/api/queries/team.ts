"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../provider";
import type {
  AuditEventList,
  OwnershipTransfer,
  TeamInvitableRole,
  TeamInvitation,
  TeamInvitationCreate,
  TeamInvitationList,
  TeamMemberList,
  WorkspacePermissions,
} from "../types";
import { keys, type AuditFilters } from "./keys";
import { expectOk, unwrap } from "./unwrap";

export const AUDIT_PAGE_SIZE = 30;

/** GR-19: the caller's role and permissions in this workspace; the UI's can() reads them. */
export function usePermissionList(wid: string) {
  const api = useApi();
  return useQuery<WorkspacePermissions>({
    queryKey: keys.permissions(wid),
    staleTime: 5 * 60_000,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/permissions", { params: { path: { wid } } })),
  });
}

export function useMembers(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<TeamMemberList>({
    queryKey: keys.members(wid),
    enabled,
    staleTime: 30_000,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/members", { params: { path: { wid } } })),
  });
}

export function useInvitations(wid: string, enabled = true) {
  const api = useApi();
  return useQuery<TeamInvitationList>({
    queryKey: keys.invitations(wid),
    enabled,
    staleTime: 30_000,
    queryFn: () => unwrap(api.GET("/v1/w/{wid}/invitations", { params: { path: { wid } } })),
  });
}

function useRefreshTeam(wid: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: keys.members(wid) });
    void queryClient.invalidateQueries({ queryKey: keys.invitations(wid) });
  };
}

export function useInviteMember(wid: string) {
  const api = useApi();
  const refresh = useRefreshTeam(wid);
  return useMutation<TeamInvitation, Error, TeamInvitationCreate>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/invitations", { params: { path: { wid } }, body })),
    onSuccess: refresh,
  });
}

export function useResendInvitation(wid: string) {
  const api = useApi();
  const refresh = useRefreshTeam(wid);
  return useMutation<TeamInvitation, Error, string>({
    mutationFn: (id) =>
      unwrap(api.POST("/v1/w/{wid}/invitations/{invitation_id}/resend", { params: { path: { wid, invitation_id: id } } })),
    onSuccess: refresh,
  });
}

export function useRevokeInvitation(wid: string) {
  const api = useApi();
  const refresh = useRefreshTeam(wid);
  return useMutation<void, Error, string>({
    mutationFn: (id) =>
      expectOk(api.DELETE("/v1/w/{wid}/invitations/{invitation_id}", { params: { path: { wid, invitation_id: id } } })),
    onSuccess: refresh,
  });
}

export function useChangeMemberRole(wid: string) {
  const api = useApi();
  const refresh = useRefreshTeam(wid);
  return useMutation<TeamMemberList, Error, { userId: string; role: TeamInvitableRole }>({
    mutationFn: ({ userId, role }) =>
      unwrap(api.PATCH("/v1/w/{wid}/members/{user_id}", { params: { path: { wid, user_id: userId } }, body: { role } })),
    onSuccess: refresh,
  });
}

export function useRemoveMember(wid: string) {
  const api = useApi();
  const refresh = useRefreshTeam(wid);
  return useMutation<void, Error, string>({
    mutationFn: (userId) =>
      expectOk(api.DELETE("/v1/w/{wid}/members/{user_id}", { params: { path: { wid, user_id: userId } } })),
    onSuccess: refresh,
  });
}

export function useTransferOwnership(wid: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation<TeamMemberList, Error, OwnershipTransfer>({
    mutationFn: (body) => unwrap(api.POST("/v1/w/{wid}/ownership-transfer", { params: { path: { wid } }, body })),
    onSuccess: () => {
      // The caller's own role changed, so everything that reads it is stale.
      void queryClient.invalidateQueries({ queryKey: keys.workspaces });
      void queryClient.invalidateQueries({ queryKey: keys.permissions(wid) });
      void queryClient.invalidateQueries({ queryKey: keys.members(wid) });
    },
  });
}

/** One page of the audit log, newest first. */
export function useAuditEvents(wid: string, filters: AuditFilters, enabled = true) {
  const api = useApi();
  return useQuery<AuditEventList>({
    queryKey: keys.auditEvents(wid, filters),
    enabled,
    staleTime: 15_000,
    queryFn: () =>
      unwrap(
        api.GET("/v1/w/{wid}/audit-events", {
          params: {
            path: { wid },
            query: {
              member: filters.member ?? undefined,
              action: filters.action ?? undefined,
              since: filters.since ?? undefined,
              limit: AUDIT_PAGE_SIZE,
              offset: filters.page * AUDIT_PAGE_SIZE,
            },
          },
        }),
      ),
  });
}
