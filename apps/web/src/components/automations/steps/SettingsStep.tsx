"use client";

import { X } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DateTimePicker } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition, SurgeOrder } from "@/lib/api/types";
import { errorsFor, isCommentTrigger, runWindowProblem, type FieldErrors } from "@/lib/automations/definition";
import { HOURS_SUMMARY, settingsSummary, SURGE_HINT, SURGE_LABEL } from "@/lib/automations/format";
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
  const stepErrors = ["cooldown_hours", "starts_at", "ends_at", "surge_order", "hours_condition"].flatMap((field) => errorsFor(errors, field));
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

          <div className="space-y-2">
            <p id="automation-hours-label" className="text-sm font-medium">
              Business hours
            </p>
            <ToggleGroup
              aria-labelledby="automation-hours-label"
              aria-describedby="automation-hours-hint"
              value={draft.hours_condition ?? "any"}
              onValueChange={(value) => {
                if (value) change({ hours_condition: value === "any" ? null : (value as "inside" | "outside") });
              }}
              className="flex-col sm:flex-row"
            >
              <ToggleGroupItem value="any">Any time</ToggleGroupItem>
              <ToggleGroupItem value="inside">{HOURS_SUMMARY.inside}</ToggleGroupItem>
              <ToggleGroupItem value="outside">{HOURS_SUMMARY.outside}</ToggleGroupItem>
            </ToggleGroup>
            <p id="automation-hours-hint" className="text-xs text-fg-secondary">
              Set your hours in{" "}
              <Link href={`/w/${slug}/settings/hours` as Route} className="text-brand-fg underline underline-offset-4">
                Settings → Business hours
              </Link>
              . An account with no hours counts as always open.
            </p>
          </div>

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

          <div className="flex items-start justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="automation-track-links">Track link clicks</Label>
              <p id="automation-track-links-hint" className="text-xs text-fg-secondary">
                {draft.track_links === false
                  ? "Link buttons are sent exactly as you wrote them, so clicks aren't counted."
                  : "Link buttons go through a Social Hood link that sends people on to yours, so each step can show its clicks. Link previews aren't counted."}
              </p>
            </div>
            <Switch
              id="automation-track-links"
              checked={draft.track_links !== false}
              onCheckedChange={(checked) => change({ track_links: checked })}
              aria-describedby="automation-track-links-hint"
              className="mt-0.5"
            />
          </div>

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
        <DateTimePicker
          idPrefix={id}
          size="lg"
          value={inputs}
          onChange={(next) => set(next.date, next.time)}
          labels={{ date: `${label} date`, time: `${label} time` }}
          hideLabels
          timeNeedsDate
          className="flex-1"
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
