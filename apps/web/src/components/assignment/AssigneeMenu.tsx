"use client";

import { ChevronDown, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAssignConversation, useAssignment, useSetAvailability } from "@/lib/api/queries";
import type { Assignable, Conversation } from "@/lib/api/types";
import { assigneeName } from "@/lib/inbox/assignee";
import { PERMISSION, useCan } from "@/lib/permissions";
import { toastError } from "@/lib/toast-error";
import { useCurrentWorkspace } from "@/lib/workspace";

import { AssigneeAvatar } from "./AssigneeAvatar";

const NOBODY = "nobody";

/**
 * Whether the caller may change the assignee to this choice. The API decides (and answers 403);
 * this only keeps the menu from offering what it would refuse: owners and admins choose anyone, an
 * agent takes a conversation nobody has and hands on or releases their own.
 */
export function mayChoose(opts: { isAdmin: boolean; youId: string | null; current: string | null; target: string | null }): boolean {
  if (opts.isAdmin) return true;
  if (opts.current !== null && opts.current === opts.youId) return true;
  return opts.current === null && opts.target !== null && opts.target === opts.youId;
}

function memberLine(member: Assignable): string {
  const parts = [member.name ?? "A team member"];
  if (member.is_you) parts.push("(you)");
  return parts.join(" ");
}

/**
 * GR-20: who has this conversation. A menu in the thread header (`header`) and a full-width
 * button in the details panel (`panel`): Nobody, then each member with how many open conversations
 * they have and whether they are away from round-robin. The last item is the caller's own
 * availability for new conversations.
 */
export function AssigneeMenu({ conversation, variant = "header" }: { conversation: Conversation; variant?: "header" | "panel" }) {
  const { id: wid } = useCurrentWorkspace();
  const overview = useAssignment(wid);
  const assign = useAssignConversation(wid);
  const availability = useSetAvailability(wid);
  const { can } = useCan();
  const members = overview.data?.members ?? [];
  const you = members.find((member) => member.is_you) ?? null;
  const isAdmin = can(PERMISSION.manageSettings);
  const current = conversation.assignee?.user_id ?? null;
  const name = conversation.assignee ? assigneeName(conversation.assignee, members) : null;
  const picture = conversation.assignee?.avatar_url ?? members.find((member) => member.user_id === current)?.avatar_url ?? null;

  const choose = (value: string) => {
    const target = value === NOBODY ? null : value;
    if (target === current) return;
    assign.mutate(
      { id: conversation.id, userId: target },
      {
        onSuccess: (done) => toast.success(done.assignee ? "Assigned" : "Assignee removed"),
        onError: (error) => toastError(error),
      },
    );
  };

  const label = name ? `Assigned to ${name}. Change` : "Assign this conversation";
  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            {variant === "panel" ? (
              <Button variant="secondary" size="sm" className="w-full justify-between" aria-label={label} loading={assign.isPending}>
                <span className="flex min-w-0 items-center gap-2">
                  {name ? <AssigneeAvatar name={name} pictureUrl={picture} /> : <UserPlus aria-hidden />}
                  <span className="truncate">{name ?? "Nobody"}</span>
                </span>
                <ChevronDown className="size-3.5" aria-hidden />
              </Button>
            ) : (
              <Button variant="ghost" size="sm" aria-label={label} loading={assign.isPending} data-testid="assignee-button">
                {name ? <AssigneeAvatar name={name} pictureUrl={picture} /> : <UserPlus aria-hidden />}
                <span className="hidden max-w-24 truncate @2xl/header:inline">{name ?? "Assign"}</span>
              </Button>
            )}
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>{name ? `Assigned to ${name}` : "Nobody has this conversation"}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuLabel>Assigned to</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={current ?? NOBODY} onValueChange={choose}>
          <DropdownMenuRadioItem value={NOBODY} disabled={!mayChoose({ isAdmin, youId: you?.user_id ?? null, current, target: null })}>
            Nobody
          </DropdownMenuRadioItem>
          {members.map((member) => (
            <DropdownMenuRadioItem
              key={member.user_id}
              value={member.user_id}
              disabled={!mayChoose({ isAdmin, youId: you?.user_id ?? null, current, target: member.user_id })}
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate">{memberLine(member)}</span>
                <span className="text-xs text-fg-secondary">
                  {member.open_conversations} open{member.available ? "" : ", away"}
                </span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        {you ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={you.available}
              onCheckedChange={(available) =>
                availability.mutate({ userId: you.user_id, available: Boolean(available) }, { onError: (error) => toastError(error) })
              }
            >
              I&apos;m available for new conversations
            </DropdownMenuCheckboxItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
