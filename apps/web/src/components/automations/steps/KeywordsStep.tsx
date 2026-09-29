"use client";

import { TriangleAlert } from "lucide-react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition, MatchMode, OverlapWarning } from "@/lib/api/types";
import { errorsFor, type FieldErrors } from "@/lib/automations/definition";
import { MATCH_HINT, MATCH_LABEL, overlapText } from "@/lib/automations/format";

import { KeywordInput } from "../KeywordInput";
import { StepCard, type StepState } from "../StepCard";

const MODES: MatchMode[] = ["word", "exact", "contains"];

/** UX-SCR-03 Keywords: chips, match mode, and overlaps with other automations (FR-AUT-15). */
export function KeywordsStep({
  draft,
  change,
  errors,
  state,
  overlaps,
}: {
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
  /** From the last save: keywords another automation of the account also uses. */
  overlaps: OverlapWarning[];
}) {
  const keywordError = errorsFor(errors, "keywords")[0] ?? null;
  const modeErrors = errorsFor(errors, "match_mode");
  const current = new Set((draft.keywords ?? []).map((keyword) => keyword.toLowerCase()));
  const shown = overlaps.filter((overlap) => current.has(overlap.keyword.toLowerCase()));

  return (
    <StepCard id="keywords" label="Keywords" state={state} errors={[...(keywordError ? [keywordError] : []), ...modeErrors]}>
      <div className="space-y-5">
        <KeywordInput
          id="automation-keywords"
          keywords={draft.keywords ?? []}
          onChange={(keywords) => change({ keywords })}
          error={keywordError}
        />
        <div className="space-y-2">
          <p id="automation-match-label" className="text-sm font-medium">
            Match
          </p>
          <ToggleGroup
            aria-labelledby="automation-match-label"
            aria-describedby="automation-match-hint"
            value={draft.match_mode}
            onValueChange={(value) => change({ match_mode: value as MatchMode })}
            className="flex-col sm:flex-row"
          >
            {MODES.map((mode) => (
              <ToggleGroupItem key={mode} value={mode}>
                {MATCH_LABEL[mode]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p id="automation-match-hint" className="text-xs text-fg-secondary">
            {MATCH_HINT[draft.match_mode]}
          </p>
        </div>
        {shown.length > 0 ? (
          <ul className="space-y-2">
            {shown.map((overlap) => {
              const text = overlapText(overlap);
              return (
                <li
                  key={`${overlap.automation_id}-${overlap.keyword}`}
                  className="flex items-start gap-2 rounded-lg bg-warning/10 px-3 py-2 text-sm text-warning"
                >
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span>
                    {text.before}
                    <strong className="font-semibold">{text.name}</strong>
                    {text.after}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </StepCard>
  );
}
