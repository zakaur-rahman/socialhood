"use client";

import { X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition, SurgeOrder } from "@/lib/api/types";
import { errorsFor, isCommentTrigger, runWindowProblem, type FieldErrors } from "@/lib/automations/definition";
import { settingsSummary, SURGE_HINT, SURGE_LABEL } from "@/lib/automations/format";
import { toZonedInputs, zonedToDate } from "@/lib/tz";

import { StepCard, type StepState } from "../StepCard";

const ORDERS: SurgeOrder[] = ["oldest_first", "newest_first", "public_only"];
const MAX_COOLDOWN = 72;

/**
 * UX-SCR-03 Settings, collapsed to one line: cooldown (FR-AUT-05), run window in the workspace
 * timezone (FR-AUT-17), order when busy (FR-AUT-10) and the workspace's disclosure line (FR-AUT-11).
 */
export function SettingsStep({
  draft,
  change,
  errors,
  state,
  timeZone,
  disclosure,
  slug,
  defaultOpen = false,
}: {
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
  timeZone: string;
  disclosure: string | null;
  slug: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  // A problem found on activation opens the settings so the field shows.
  const [hadError, setHadError] = useState(false);
  if ((state === "error") !== hadError) {
    setHadError(state === "error");
    if (state === "error") setOpen(true);
  }
  const expanded = open;
  const stepErrors = ["cooldown_hours", "starts_at", "ends_at", "surge_order"].flatMap((field) => errorsFor(errors, field));
  const windowProblem = runWindowProblem(draft);

  return (
    <StepCard
      id="settings"
      label="Settings"
      state={state}
      errors={stepErrors}
      action={
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={expanded}
          aria-controls="automation-settings"
          onClick={() => setOpen(!open)}
        >
          {expanded ? "Done" : "Edit"}
        </Button>
      }
    >
      <p className="text-sm text-fg-secondary">{settingsSummary(draft, timeZone, disclosure)}</p>
      {expanded ? (
        <div id="automation-settings" className="mt-5 space-y-6 border-t border-line pt-5">
          <Cooldown value={draft.cooldown_hours} onChange={(hours) => change({ cooldown_hours: hours })} />

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">Run window</legend>
            <p className="text-xs text-fg-secondary">
              Optional. Times are in {timeZone}. At the end it pauses itself and tells you.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <WindowEdge
                id="automation-starts"
                label="Starts"
                value={draft.starts_at ?? null}
                defaultTime="00:00"
                timeZone={timeZone}
                onChange={(iso) => change({ starts_at: iso })}
              />
              <WindowEdge
                id="automation-ends"
                label="Ends"
                value={draft.ends_at ?? null}
                defaultTime="23:59"
                timeZone={timeZone}
                onChange={(iso) => change({ ends_at: iso })}
              />
            </div>
            {windowProblem ? <p className="text-xs text-danger-fg">{windowProblem}</p> : null}
          </fieldset>

          {isCommentTrigger(draft.trigger) ? (
            <div className="space-y-2">
              <p id="automation-order-label" className="text-sm font-medium">
                Order when busy
              </p>
              <ToggleGroup
                aria-labelledby="automation-order-label"
                aria-describedby="automation-order-hint"
                value={draft.surge_order}
                onValueChange={(value) => change({ surge_order: value as SurgeOrder })}
                className="flex-col sm:flex-row"
              >
                {ORDERS.map((order) => (
                  <ToggleGroupItem key={order} value={order}>
                    {SURGE_LABEL[order]}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              <p id="automation-order-hint" className="text-xs text-fg-secondary">
                Instagram allows 750 DMs an hour per account; more wait in a queue. {SURGE_HINT[draft.surge_order]}
              </p>
            </div>
          ) : null}

          <div className="space-y-1">
            <p className="text-sm font-medium">Disclosure</p>
            <p className="text-sm text-fg-secondary">
              {disclosure
                ? `Automated messages end with “${disclosure}”.`
                : "Automated messages don't add a disclosure line."}{" "}
              {/* Underlined at rest: in a line of text, colour alone doesn't mark a link (WCAG 1.4.1). */}
              <Link href={`/w/${slug}/settings/workspace` as Route} className="text-brand-fg underline underline-offset-4">
                Change it in Settings → Workspace
              </Link>
            </p>
          </div>
        </div>
      ) : null}
    </StepCard>
  );
}

/** Hours between two runs for the same person; typed as a number, kept within 0–72. */
function Cooldown({ value, onChange }: { value: number; onChange: (hours: number) => void }) {
  const [text, setText] = useState(String(value));
  const [synced, setSynced] = useState(value);
  if (value !== synced) {
    setSynced(value);
    setText(String(value));
  }
  const parsed = Number(text);
  const invalid = text.trim() === "" || !Number.isInteger(parsed) || parsed < 0 || parsed > MAX_COOLDOWN;
  return (
    <div className="space-y-2">
      <Label htmlFor="automation-cooldown">Once per person every</Label>
      <div className="flex items-center gap-2">
        <Input
          id="automation-cooldown"
          type="number"
          inputMode="numeric"
          min={0}
          max={MAX_COOLDOWN}
          step={1}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            const next = Number(event.target.value);
            if (event.target.value.trim() !== "" && Number.isInteger(next) && next >= 0 && next <= MAX_COOLDOWN) {
              setSynced(next);
              onChange(next);
            }
          }}
          aria-invalid={invalid ? true : undefined}
          aria-describedby="automation-cooldown-hint"
          size="lg"
          className="w-24"
        />
        <span className="text-sm text-fg-secondary">hours</span>
      </div>
      <p id="automation-cooldown-hint" className={invalid ? "text-xs text-danger-fg" : "text-xs text-fg-secondary"}>
        {invalid
          ? `Use a whole number from 0 to ${MAX_COOLDOWN}.`
          : "0 answers every time. A comment is only ever answered once."}
      </p>
    </div>
  );
}

/** One end of the run window: a date and a time in the workspace timezone. */
function WindowEdge({
  id,
  label,
  value,
  defaultTime,
  timeZone,
  onChange,
}: {
  id: string;
  label: string;
  value: string | null;
  defaultTime: string;
  timeZone: string;
  onChange: (iso: string | null) => void;
}) {
  const inputs = value ? toZonedInputs(new Date(value), timeZone) : { date: "", time: "" };
  const set = (date: string, time: string) => {
    if (!date) return onChange(null);
    const instant = zonedToDate(date, time || defaultTime, timeZone);
    if (instant) onChange(instant.toISOString());
  };
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-fg-secondary">{label}</p>
      <div className="flex items-center gap-2">
        <label htmlFor={`${id}-date`} className="sr-only">
          {label} date
        </label>
        <Input
          id={`${id}-date`}
          type="date"
          value={inputs.date}
          onChange={(event) => set(event.target.value, inputs.time)}
          size="lg"
        />
        <label htmlFor={`${id}-time`} className="sr-only">
          {label} time
        </label>
        <Input
          id={`${id}-time`}
          type="time"
          value={inputs.time}
          disabled={!inputs.date}
          onChange={(event) => set(inputs.date, event.target.value)}
          size="lg"
          className="w-28"
        />
        {value ? (
          <Button variant="ghost" size="icon-lg" aria-label={`Clear ${label.toLowerCase()}`} onClick={() => onChange(null)}>
            <X aria-hidden />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
