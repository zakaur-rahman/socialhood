"use client";

import { usePermissionList } from "@/lib/api/queries";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * The permission names the UI asks about. The matrix itself lives in the API
 * (auth/permissions.py) and arrives from GET /v1/w/{wid}/permissions; nothing here says which
 * role has which.
 */
export const PERMISSION = {
  reply: "inbox.reply",
  manageAutomations: "automations.manage",
  manageKnowledge: "knowledge.manage",
  manageSettings: "settings.manage",
  manageBilling: "billing.manage",
  readAudit: "audit.read",
  readMembers: "members.read",
  inviteMembers: "members.invite",
  manageMembers: "members.manage",
  transferOwnership: "ownership.transfer",
  deleteWorkspace: "workspace.delete",
} as const;

export type PermissionName = (typeof PERMISSION)[keyof typeof PERMISSION];

/**
 * `can(permission)` for the current workspace. While the list loads, or if it fails, nothing is
 * allowed, so a control never shows for a moment and then goes away.
 */
export function useCan(): { can: (permission: PermissionName) => boolean; ready: boolean } {
  const { id } = useCurrentWorkspace();
  const list = usePermissionList(id);
  const granted = list.data?.permissions;
  return { can: (permission) => granted?.includes(permission) ?? false, ready: list.isSuccess };
}
