"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition } from "@/lib/api/types";
import { errorsFor, type FieldErrors } from "@/lib/automations/definition";

import { StepCard, type StepState } from "../StepCard";

type Scope = "all" | "selected";

const MAX_ADS = 20;

const SCOPES: { value: Scope; label: string; hint: string }[] = [
  { value: "all", label: "Any ad", hint: "Chats opened from any of your ads, including new ones." },
  {
    value: "selected",
    label: "Chosen ads",
    hint: "Only chats opened from the ads you list below. Find an ad's id in Ads Manager.",
  },
];

/**
 * GR-09, the posts slot of an ad click: any ad, or ad ids typed by hand. Listing the account's
 * ads would need Meta's ads_read permission, which Amplychat does not ask for.
 */
export function AdsStep({
  draft,
  change,
  errors,
  state,
}: {
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
}) {
  const selected = draft.post_scope === "selected";
  const chosen = draft.ad_ids ?? [];
  const [typed, setTyped] = useState("");
  const stepErrors = ["post_scope", "ad_ids"].flatMap((field) => errorsFor(errors, field));
  const hint = SCOPES.find((scope) => scope.value === (selected ? "selected" : "all"))?.hint;

  function add() {
    const id = typed.trim();
    if (!id || chosen.includes(id) || chosen.length >= MAX_ADS) return;
    change({ ad_ids: [...chosen, id] });
    setTyped("");
  }

  return (
    <StepCard id="posts" label="On these ads" state={state} errors={stepErrors}>
      <div className="space-y-4">
        <div className="space-y-2">
          <ToggleGroup
            aria-label="Which ads"
            aria-describedby="automation-ad-scope-hint"
            value={selected ? "selected" : "all"}
            onValueChange={(value) => change({ post_scope: value as Scope })}
            className="flex-col sm:flex-row"
          >
            {SCOPES.map((scope) => (
              <ToggleGroupItem key={scope.value} value={scope.value}>
                {scope.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p id="automation-ad-scope-hint" className="text-xs text-fg-secondary">
            {hint}
          </p>
        </div>

        {selected ? (
          <div className="space-y-3">
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                add();
              }}
            >
              <Input
                aria-label="Ad id"
                placeholder="Ad id, for example 120210000000000"
                inputMode="numeric"
                maxLength={64}
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
              />
              <Button type="submit" variant="secondary" disabled={!typed.trim() || chosen.length >= MAX_ADS}>
                Add
              </Button>
            </form>
            {chosen.length > 0 ? (
              <ul className="flex flex-wrap gap-2" aria-label="Chosen ads">
                {chosen.map((id) => (
                  <li key={id} className="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-sm">
                    <span className="tabular-nums">{id}</span>
                    <button
                      type="button"
                      aria-label={`Remove ad ${id}`}
                      className="text-fg-secondary hover:text-fg"
                      onClick={() => change({ ad_ids: chosen.filter((x) => x !== id) })}
                    >
                      <X className="size-3.5" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-fg-secondary">No ads yet. Add the id of each ad to answer.</p>
            )}
          </div>
        ) : null}
      </div>
    </StepCard>
  );
}
