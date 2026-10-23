"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useSetLeadStage } from "@/lib/api/queries";
import type { ContactRecord, LeadStage } from "@/lib/api/types";
import { STAGE_LABEL, STAGE_TONE } from "@/lib/leads/stages";
import { toastError } from "@/lib/toast-error";
import { formatDay } from "@/lib/tz";
import { useCurrentWorkspace } from "@/lib/workspace";

import { StageControl } from "./StageControl";

/**
 * A contact's lead stage in the contact drawer (GR-18): the stage, why it is there and since when,
 * a gone-cold flag, and a control to move it with an optional note. The history of moves (who or
 * what, and why) is in the timeline below.
 */
export function LeadStageSection({ record }: { record: ContactRecord }) {
  const { id: wid, timezone } = useCurrentWorkspace();
  const move = useSetLeadStage(wid);
  const [note, setNote] = useState("");

  function change(stage: LeadStage) {
    move.mutate(
      { id: record.id, stage, note },
      {
        onSuccess: () => {
          setNote("");
          toast.success(`Moved to ${STAGE_LABEL[stage]}`);
        },
        onError: (error) => toastError(error),
      },
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STAGE_TONE[record.lead_stage]} size="md" data-testid="lead-stage">
          {STAGE_LABEL[record.lead_stage]}
        </Badge>
        {record.lead_cold ? (
          <Badge tone="warning" size="md">
            Gone cold
          </Badge>
        ) : null}
        {record.lead_stage_at ? (
          <span className="text-xs text-fg-secondary">Since {formatDay(record.lead_stage_at, timezone)}</span>
        ) : null}
      </div>
      {record.lead_stage_reason ? <p className="text-sm text-fg-secondary">{record.lead_stage_reason}</p> : null}
      <StageControl value={record.lead_stage} onChange={change} label="Lead stage" disabled={move.isPending} className="sm:w-56" />
      <Input
        aria-label="Why? (optional)"
        placeholder="Why? (optional)"
        maxLength={300}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        className="sm:w-80"
      />
    </div>
  );
}
