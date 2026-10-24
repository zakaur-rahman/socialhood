"use client";

import { Crown, Mail, Plus, RotateCw, Trash2, UserMinus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { AssignmentCard } from "./AssignmentCard";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import {
  useChangeMemberRole,
  useInvitations,
  useInviteMember,
  useMembers,
  useRemoveMember,
  useResendInvitation,
  useRevokeInvitation,
  useTransferOwnership,
} from "@/lib/api/queries";
import type { TeamInvitableRole, TeamInvitation, TeamMember, TeamSeats } from "@/lib/api/types";
import { PERMISSION, useCan } from "@/lib/permissions";
import { toastError } from "@/lib/toast-error";
import { relativeTime } from "@/lib/time";
import { useCurrentWorkspace } from "@/lib/workspace";

const ROLE_LABEL = { owner: "Owner", admin: "Admin", agent: "Agent" } as const;
const ROLE_HELP: Record<TeamInvitableRole, string> = {
  admin: "Admins also edit automations, knowledge and settings.",
  agent: "Agents reply to customers, tag contacts and assign conversations.",
};

function seatSummary(seats: TeamSeats): string {
  const pending = seats.pending_invitations;
  const used = `${seats.members} of ${seats.limit ?? "unlimited"} seat${seats.limit === 1 ? "" : "s"} used`;
  return pending > 0 ? `${used}, plus ${pending} pending invitation${pending === 1 ? "" : "s"}.` : `${used}.`;
}

/**
 * GR-19: Settings → Members. Who can work in the workspace and as what. Owners and admins see the
 * list and invite (admins invite agents only); owners change roles, remove people and hand over
 * ownership. What each person may do comes from the API (`useCan`), never from the role name.
 */
export function MembersPage() {
  const workspace = useCurrentWorkspace();
  const wid = workspace.id;
  const { can, ready } = useCan();
  const canRead = can(PERMISSION.readMembers);
  const members = useMembers(wid, canRead);
  const invitations = useInvitations(wid, canRead);
  const [inviting, setInviting] = useState(false);
  const [removing, setRemoving] = useState<TeamMember | null>(null);
  const [transferring, setTransferring] = useState<TeamMember | null>(null);
  const [revoking, setRevoking] = useState<TeamInvitation | null>(null);
  const change = useChangeMemberRole(wid);
  const remove = useRemoveMember(wid);
  const resend = useResendInvitation(wid);
  const revoke = useRevokeInvitation(wid);
  const canManage = can(PERMISSION.manageMembers);
  const canTransfer = can(PERMISSION.transferOwnership);

  let content;
  if (!ready || (canRead && (members.isPending || invitations.isPending))) {
    content = (
      <Card>
        <ul aria-busy="true" aria-label="Loading members" className="divide-y divide-line-subtle">
          {Array.from({ length: 3 }, (_, i) => (
            <li key={i} className="space-y-2 px-4 py-4">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
            </li>
          ))}
        </ul>
      </Card>
    );
  } else if (!canRead) {
    content = (
      <Card>
        <EmptyState
          size="compact"
          icon={<UserMinus />}
          title="Members are for owners and admins"
          body="Ask an owner or admin of this workspace if you need to see who has access."
        />
      </Card>
    );
  } else if (members.isError) {
    content = <ErrorState error={members.error} onRetry={() => void members.refetch()} />;
  } else if (invitations.isError) {
    content = <ErrorState error={invitations.error} onRetry={() => void invitations.refetch()} />;
  } else if (!members.data || !invitations.data) {
    content = null;
  } else {
    const pending = invitations.data.items;
    content = (
      <div className="space-y-6">
        <p className="text-sm text-fg-secondary" data-testid="seat-summary">
          {seatSummary(members.data.seats)}
        </p>
        <Card className="overflow-hidden p-0">
          <ul aria-label="Members" className="divide-y divide-line-subtle">
            {members.data.items.map((member) => {
              const label = member.name ?? member.email;
              const editable = canManage && !member.is_you && member.role !== "owner";
              return (
                <li key={member.user_id} className="space-y-2 px-4 py-4" data-testid="member-row">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-0.5">
                      <p className="truncate text-sm font-medium">
                        {label}
                        {member.is_you ? <span className="ms-2 text-xs text-fg-secondary">(you)</span> : null}
                      </p>
                      {member.name ? <p className="truncate text-sm text-fg-secondary">{member.email}</p> : null}
                      <p className="text-xs text-fg-secondary">
                        {member.last_seen_at ? `Last active ${relativeTime(member.last_seen_at)}` : "Not active yet"}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      {editable ? (
                        <Select
                          value={member.role}
                          onValueChange={(role) =>
                            change.mutate(
                              { userId: member.user_id, role: role as TeamInvitableRole },
                              {
                                onSuccess: () => toast.success(`${label} is now ${ROLE_LABEL[role as TeamInvitableRole].toLowerCase()}`),
                                onError: (error) => toastError(error),
                              },
                            )
                          }
                        >
                          <SelectTrigger aria-label={`Role of ${label}`} className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="agent">Agent</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : (
                        <Badge tone={member.role === "owner" ? "brand" : "neutral"}>{ROLE_LABEL[member.role]}</Badge>
                      )}
                      {canTransfer && !member.is_you ? (
                        <Button variant="ghost" size="sm" onClick={() => setTransferring(member)} aria-label={`Make ${label} the owner`}>
                          <Crown aria-hidden /> Make owner
                        </Button>
                      ) : null}
                      {editable ? (
                        <Button
                          variant="destructive-ghost"
                          size="sm"
                          onClick={() => setRemoving(member)}
                          aria-label={`Remove ${label}`}
                        >
                          <Trash2 aria-hidden /> Remove
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>

        <AssignmentCard />

        <section aria-labelledby="pending-invitations" className="space-y-3">
          <h2 id="pending-invitations" className="text-base font-semibold">
            Pending invitations
          </h2>
          {pending.length === 0 ? (
            <Card>
              <EmptyState size="compact" icon={<Mail />} title="No pending invitations" body="Invite someone and they show up here until they join." />
            </Card>
          ) : (
            <Card className="overflow-hidden p-0">
              <ul aria-label="Pending invitations" className="divide-y divide-line-subtle">
                {pending.map((invitation) => (
                  <li key={invitation.id} className="space-y-2 px-4 py-4" data-testid="invitation-row">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 space-y-0.5">
                        <p className="truncate text-sm font-medium">{invitation.email}</p>
                        <p className="text-xs text-fg-secondary">
                          {ROLE_LABEL[invitation.role]}
                          {invitation.invited_by_name ? `, invited by ${invitation.invited_by_name}` : ""}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        <Badge tone={invitation.status === "expired" ? "warning" : "neutral"}>
                          {invitation.status === "expired" ? "Expired" : "Pending"}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={resend.isPending && resend.variables === invitation.id}
                          onClick={() =>
                            resend.mutate(invitation.id, {
                              onSuccess: () => toast.success(`Invitation sent again to ${invitation.email}`),
                              onError: (error) => toastError(error),
                            })
                          }
                          aria-label={`Resend the invitation to ${invitation.email}`}
                        >
                          <RotateCw aria-hidden /> Resend
                        </Button>
                        <Button
                          variant="destructive-ghost"
                          size="sm"
                          onClick={() => setRevoking(invitation)}
                          aria-label={`Revoke the invitation to ${invitation.email}`}
                        >
                          Revoke
                        </Button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </section>
      </div>
    );
  }

  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          title="Members"
          description="The people who work in this workspace and what each of them can do."
          actions={
            can(PERMISSION.inviteMembers) ? (
              <Button size="lg" onClick={() => setInviting(true)}>
                <Plus aria-hidden /> Invite <span className="max-[359px]:sr-only">someone</span>
              </Button>
            ) : null
          }
        />
      }
    >
      {content}
      {can(PERMISSION.inviteMembers) ? (
        <InviteDialog
          key={inviting ? "open" : "closed"}
          wid={wid}
          open={inviting}
          onOpenChange={setInviting}
          canInviteAdmins={canManage}
        />
      ) : null}
      {transferring ? (
        <TransferDialog
          key={transferring.user_id}
          wid={wid}
          workspaceName={workspace.name}
          member={transferring}
          onClose={() => setTransferring(null)}
        />
      ) : null}
      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing?.name ?? removing?.email}?</AlertDialogTitle>
            <AlertDialogDescription>
              They lose access to this workspace at once. Messages they sent and changes they made stay, under their name.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep them</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (!removing) return;
                remove.mutate(removing.user_id, {
                  onSuccess: () => toast.success("Member removed"),
                  onError: (error) => toastError(error),
                });
              }}
            >
              Remove member
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={revoking !== null} onOpenChange={(open) => !open && setRevoking(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke the invitation?</AlertDialogTitle>
            <AlertDialogDescription>
              {revoking?.email} can no longer join with it. You can invite them again later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (!revoking) return;
                revoke.mutate(revoking.id, {
                  onSuccess: () => toast.success("Invitation revoked"),
                  onError: (error) => toastError(error),
                });
              }}
            >
              Revoke invitation
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsFrame>
  );
}

function InviteDialog({
  wid,
  open,
  onOpenChange,
  canInviteAdmins,
}: {
  wid: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  canInviteAdmins: boolean;
}) {
  const invite = useInviteMember(wid);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<TeamInvitableRole>("agent");
  const [problem, setProblem] = useState<string | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setProblem(null);
    invite.mutate(
      { email: email.trim(), role },
      {
        onSuccess: (created) => {
          onOpenChange(false);
          toast.success(`Invitation sent to ${created.email}`);
        },
        onError: (error) => {
          if (error instanceof ApiError && (error.code === "conflict" || error.errors.length > 0)) {
            setProblem(error.errors[0]?.message ?? error.message);
          } else {
            toastError(error);
          }
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Invite someone</DialogTitle>
            <DialogDescription>
              They get an email with a link to join. The invitation holds a seat on your plan until they accept or you revoke it.
            </DialogDescription>
          </DialogHeader>
          <Field invalid={Boolean(problem)}>
            <FieldLabel htmlFor="invite-email">Email</FieldLabel>
            <Input
              id="invite-email"
              type="email"
              required
              maxLength={254}
              autoComplete="off"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            {problem ? <p className="text-sm text-danger-fg">{problem}</p> : null}
          </Field>
          <Field>
            <FieldLabel htmlFor="invite-role">Role</FieldLabel>
            <Select value={role} onValueChange={(value) => setRole(value as TeamInvitableRole)}>
              <SelectTrigger id="invite-role" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {canInviteAdmins ? <SelectItem value="admin">Admin</SelectItem> : null}
                <SelectItem value="agent">Agent</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-fg-secondary">{ROLE_HELP[role]}</p>
          </Field>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={invite.isPending} disabled={!email.trim()}>
              Send invitation
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Ownership moves to one person and the current owner becomes an admin; typing the name confirms it. */
function TransferDialog({
  wid,
  workspaceName,
  member,
  onClose,
}: {
  wid: string;
  workspaceName: string;
  member: TeamMember;
  onClose: () => void;
}) {
  const transfer = useTransferOwnership(wid);
  const [confirmName, setConfirmName] = useState("");
  const label = member.name ?? member.email;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    transfer.mutate(
      { user_id: member.user_id, confirm_name: confirmName },
      {
        onSuccess: () => {
          onClose();
          toast.success(`${label} is now the owner`);
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Make {label} the owner?</DialogTitle>
            <DialogDescription>
              They take over billing, members and deleting the workspace. You become an admin and can&apos;t undo this yourself.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="transfer-confirm">Type {workspaceName} to confirm</FieldLabel>
            <Input
              id="transfer-confirm"
              required
              maxLength={200}
              autoComplete="off"
              value={confirmName}
              onChange={(event) => setConfirmName(event.target.value)}
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" loading={transfer.isPending} disabled={confirmName.trim() !== workspaceName.trim()}>
              Make owner
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
