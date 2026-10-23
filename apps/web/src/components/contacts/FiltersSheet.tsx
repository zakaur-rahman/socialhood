"use client";

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useContactFields, useTags } from "@/lib/api/queries";
import type { ConsentChannel, LeadStage, Platform } from "@/lib/api/types";
import {
  ACTIVITY_RANGES,
  EMPTY_FILTERS,
  MAX_FIELD_FILTERS,
  MAX_TAG_FILTERS,
  type ActivityRange,
  type ContactFilters,
  type FieldFilter,
} from "@/lib/contacts/filters";
import { LEAD_STAGES } from "@/lib/leads/stages";
import { useCurrentWorkspace } from "@/lib/workspace";

import { TagChip } from "./TagChip";

const ANY = "any";
const YES = "yes";
const NO = "no";

/** A three-way choice (any, yes, no) kept as a nullable boolean in the filters. */
function triState(value: boolean | null): string {
  return value === null ? ANY : value ? YES : NO;
}
function fromTriState(value: string): boolean | null {
  return value === ANY ? null : value === YES;
}

/**
 * The filters (GR-17): tag (every one chosen), lead stage (GR-18, any one chosen), email and phone,
 * platform, marketing consent, lead score, last activity and up to five custom field conditions (has a value, or equals one). They
 * apply as you change them; the list filters on the server.
 */
export function FiltersSheet({
  open,
  onOpenChange,
  filters,
  onChange,
  hideStage = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  filters: ContactFilters;
  onChange: (next: ContactFilters) => void;
  /** The Leads view is already split by stage, so it leaves the stage filter out. */
  hideStage?: boolean;
}) {
  const { id: wid } = useCurrentWorkspace();
  const tags = useTags(wid).data ?? [];
  const definitions = useContactFields(wid).data?.items ?? [];
  const set = (patch: Partial<ContactFilters>) => onChange({ ...filters, ...patch });

  function toggleTag(id: string, on: boolean) {
    set({ tagIds: on ? [...filters.tagIds, id].slice(0, MAX_TAG_FILTERS) : filters.tagIds.filter((t) => t !== id) });
  }
  function toggleStage(stage: LeadStage, on: boolean) {
    set({ stages: on ? [...filters.stages, stage] : filters.stages.filter((s) => s !== stage) });
  }
  function setFieldRow(index: number, patch: Partial<FieldFilter>) {
    set({ fields: filters.fields.map((row, i) => (i === index ? { ...row, ...patch } : row)) });
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent size="panel" className="gap-0">
        <SheetHeader>
          <SheetTitle>Filters</SheetTitle>
          <SheetDescription>Show only the contacts that match all of these.</SheetDescription>
        </SheetHeader>
        <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-4">
          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-medium">Tags</legend>
            {tags.length === 0 ? (
              <p className="text-sm text-fg-secondary">No tags yet. Tag a contact to filter by it.</p>
            ) : (
              <ul className="space-y-1">
                {tags.map((tag) => (
                  <li key={tag.id}>
                    <label className="flex min-h-8 items-center gap-2 text-sm pointer-coarse:min-h-10">
                      <Checkbox
                        checked={filters.tagIds.includes(tag.id)}
                        onCheckedChange={(on) => toggleTag(tag.id, on === true)}
                        aria-label={`Tag ${tag.name}`}
                      />
                      <TagChip tag={tag} />
                      <span className="text-xs text-fg-secondary">{tag.contact_count}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>

          {hideStage ? null : (
            <fieldset className="space-y-2">
              <legend className="mb-1 text-sm font-medium">Lead stage</legend>
              <ul className="space-y-1">
                {LEAD_STAGES.map((stage) => (
                  <li key={stage.value}>
                    <label className="flex min-h-8 items-center gap-2 text-sm pointer-coarse:min-h-10">
                      <Checkbox
                        checked={filters.stages.includes(stage.value)}
                        onCheckedChange={(on) => toggleStage(stage.value, on === true)}
                        aria-label={`Stage ${stage.label}`}
                      />
                      {stage.label}
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          )}

          <Field>
            <FieldLabel>Email</FieldLabel>
            <Select value={triState(filters.hasEmail)} onValueChange={(v) => set({ hasEmail: fromTriState(v) })}>
              <SelectTrigger aria-label="Email" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any</SelectItem>
                <SelectItem value={YES}>Has an email</SelectItem>
                <SelectItem value={NO}>No email</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Phone</FieldLabel>
            <Select value={triState(filters.hasPhone)} onValueChange={(v) => set({ hasPhone: fromTriState(v) })}>
              <SelectTrigger aria-label="Phone" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any</SelectItem>
                <SelectItem value={YES}>Has a phone number</SelectItem>
                <SelectItem value={NO}>No phone number</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Platform</FieldLabel>
            <Select value={filters.platform ?? ANY} onValueChange={(v) => set({ platform: v === ANY ? null : (v as Platform) })}>
              <SelectTrigger aria-label="Platform" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any platform</SelectItem>
                <SelectItem value="instagram">Instagram</SelectItem>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Marketing consent</FieldLabel>
            <Select value={filters.consent ?? ANY} onValueChange={(v) => set({ consent: v === ANY ? null : (v as ConsentChannel) })}>
              <SelectTrigger aria-label="Marketing consent" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>Any</SelectItem>
                <SelectItem value="instagram">Agreed on Instagram</SelectItem>
                <SelectItem value="whatsapp">Agreed on WhatsApp</SelectItem>
                <SelectItem value="email">Agreed by email</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel>Lead score at least</FieldLabel>
            <Input
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              placeholder="Any"
              value={filters.minLeadScore ?? ""}
              onChange={(e) => {
                const text = e.target.value;
                set({ minLeadScore: text === "" ? null : Math.max(0, Math.min(100, Math.round(Number(text)))) });
              }}
            />
          </Field>
          <Field>
            <FieldLabel>Last activity</FieldLabel>
            <Select value={filters.activity} onValueChange={(v) => set({ activity: v as ActivityRange })}>
              <SelectTrigger aria-label="Last activity" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACTIVITY_RANGES.map((range) => (
                  <SelectItem key={range.value} value={range.value}>
                    {range.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          {definitions.length > 0 ? (
            <fieldset className="space-y-3">
              <legend className="mb-1 text-sm font-medium">Custom fields</legend>
              {filters.fields.map((row, index) => (
                <div key={index} className="space-y-2 rounded-lg border border-line p-3" data-testid="field-filter">
                  <div className="flex items-center gap-2">
                    <Select value={row.key || ANY} onValueChange={(v) => setFieldRow(index, { key: v === ANY ? "" : v })}>
                      <SelectTrigger aria-label="Field" className="min-w-0 flex-1">
                        <SelectValue placeholder="Choose a field" />
                      </SelectTrigger>
                      <SelectContent>
                        {definitions.map((d) => (
                          <SelectItem key={d.key} value={d.key}>
                            {d.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Remove this field condition"
                      onClick={() => set({ fields: filters.fields.filter((_, i) => i !== index) })}
                    >
                      <X aria-hidden />
                    </Button>
                  </div>
                  <Select value={row.mode} onValueChange={(v) => setFieldRow(index, { mode: v as FieldFilter["mode"] })}>
                    <SelectTrigger aria-label="Condition" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="has">Has a value</SelectItem>
                      <SelectItem value="equals">Equals</SelectItem>
                    </SelectContent>
                  </Select>
                  {row.mode === "equals" ? (
                    <Input
                      aria-label="Value"
                      maxLength={60}
                      value={row.value}
                      onChange={(e) => setFieldRow(index, { value: e.target.value })}
                    />
                  ) : null}
                </div>
              ))}
              {filters.fields.length < MAX_FIELD_FILTERS ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => set({ fields: [...filters.fields, { key: "", mode: "has", value: "" }] })}
                >
                  <Plus aria-hidden /> Add a field condition
                </Button>
              ) : null}
            </fieldset>
          ) : null}
        </div>
        <SheetFooter className="flex-row justify-between border-t border-line">
          <Button variant="ghost" onClick={() => onChange({ ...EMPTY_FILTERS, q: filters.q })}>
            Clear filters
          </Button>
          <Button onClick={() => onOpenChange(false)}>Done</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
