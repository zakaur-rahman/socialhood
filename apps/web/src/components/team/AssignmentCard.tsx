"use client";

import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useAssignment, useSetAvailability, useSetRoundRobin } from "@/lib/api/queries";
import { PERMISSION, useCan } from "@/lib/permissions";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

/**
 * GR-20: how new conversations are handed out. Round-robin (off by default) gives a new
 * conversation nobody has to the next available member in turn; each member has an availability
 * switch (yours, or anyone's as an owner or admin). Assigning by hand ignores availability.
 * Shows nothing while loading or if the list fails: the members above it are the page.
 */
export function AssignmentCard() {
  const { id: wid } = useCurrentWorkspace();
  const overview = useAssignment(wid);
  const setRoundRobin = useSetRoundRobin(wid);
  const setAvailable = useSetAvailability(wid);
  const { can } = useCan();
  const canSetup = can(PERMISSION.manageSettings);
  if (!overview.data) return null;
  const { round_robin: roundRobin, members } = overview.data;

  return (
    <Card className="space-y-4 p-4" aria-labelledby="assignment-heading">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <h2 id="assignment-heading" className="text-sm font-semibold">
            Hand out new conversations
          </h2>
          <p className="text-sm text-fg-secondary">
            With round-robin on, a new conversation nobody has goes to the next available member in turn. You can still
            assign any conversation by hand.
          </p>
        </div>
        <Switch
          checked={roundRobin}
          disabled={!canSetup || setRoundRobin.isPending}
          onCheckedChange={(on) => setRoundRobin.mutate(on, { onError: (error) => toastError(error) })}
          aria-label="Round-robin"
        />
      </div>
      <ul aria-label="Availability" className="divide-y divide-line-subtle border-t border-line-subtle">
        {members.map((member) => {
          const label = member.name ?? "A team member";
          const editable = member.is_you || canSetup;
          return (
            <li key={member.user_id} className="flex items-center justify-between gap-3 py-3" data-testid="availability-row">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {label}
                  {member.is_you ? <span className="ms-2 text-xs text-fg-secondary">(you)</span> : null}
                </p>
                <p className="text-xs text-fg-secondary">
                  {member.open_conversations} open conversation{member.open_conversations === 1 ? "" : "s"}
                </p>
              </div>
              <Switch
                checked={member.available}
                disabled={!editable || setAvailable.isPending}
                onCheckedChange={(available) =>
                  setAvailable.mutate({ userId: member.user_id, available }, { onError: (error) => toastError(error) })
                }
                aria-label={`${label} is available`}
              />
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
