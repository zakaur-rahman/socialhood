"use client";

import { MessageCircle, MessagesSquare, Send } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition, SocialAccount, TriggerName } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { errorsFor, type FieldErrors } from "@/lib/automations/definition";
import { TRIGGER_LABEL } from "@/lib/automations/format";

import { StepCard, type StepState } from "../StepCard";

const TRIGGERS: { value: TriggerName; icon: typeof Send; hint: string }[] = [
  { value: "comment_keyword", icon: MessageCircle, hint: "Someone comments one of your keywords on a post." },
  { value: "comment_any", icon: MessagesSquare, hint: "Anyone comments on the posts you choose." },
  { value: "dm_keyword", icon: Send, hint: "Someone sends a DM with one of your keywords." },
];

/** UX-SCR-03 When: the Instagram account and the trigger. */
export function WhenStep({
  draft,
  change,
  errors,
  state,
  accounts,
  slug,
}: {
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
  accounts: SocialAccount[];
  slug: string;
}) {
  const accountError = errorsFor(errors, "social_account_id")[0];
  const triggerError = errorsFor(errors, "trigger")[0];
  const hint = TRIGGERS.find((trigger) => trigger.value === draft.trigger)?.hint ?? "Choose what starts this automation.";
  const known = accounts.some((account) => account.id === draft.social_account_id);

  const setTrigger = (value: TriggerName) => {
    const patch: Partial<AutomationDefinition> = { trigger: value };
    // Any comment needs chosen posts or the next post (FR-AUT-02); start it on chosen posts.
    if (value === "comment_any" && draft.post_scope === "all") patch.post_scope = "selected";
    change(patch);
  };

  return (
    <StepCard id="when" label="When" state={state} errors={[accountError, triggerError].filter(Boolean) as string[]}>
      <div className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="automation-account">Instagram account</Label>
          {accounts.length === 0 ? (
            <p className="text-sm text-fg-secondary">
              Connect an Instagram account to use automations.{" "}
              <Link
                href={`/w/${slug}/settings/connections` as Route}
                className="text-brand-fg underline-offset-4 hover:underline"
              >
                Connect Instagram
              </Link>
            </p>
          ) : (
            <Select
              value={draft.social_account_id ?? ""}
              onValueChange={(value) =>
                // Posts belong to one account, so a new account starts with none chosen.
                change({ social_account_id: value, media_item_ids: [], scheduled_post_ids: [] })
              }
            >
              <SelectTrigger
                id="automation-account"
                className="h-9 min-w-56"
                aria-invalid={accountError ? true : undefined}
              >
                <SelectValue placeholder="Choose an account" />
              </SelectTrigger>
              <SelectContent>
                {!known && draft.social_account_id ? (
                  <SelectItem value={draft.social_account_id} disabled>
                    Disconnected account
                  </SelectItem>
                ) : null}
                {accounts.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {accountLabel(account)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        <div className="space-y-2">
          <p id="automation-trigger-label" className="text-sm font-medium">
            Trigger
          </p>
          <ToggleGroup
            aria-labelledby="automation-trigger-label"
            aria-describedby="automation-trigger-hint"
            value={draft.trigger ?? ""}
            onValueChange={(value) => setTrigger(value as TriggerName)}
            className="flex-col sm:flex-row"
          >
            {TRIGGERS.map(({ value, icon: Icon }) => (
              <ToggleGroupItem key={value} value={value}>
                <Icon className="size-4" aria-hidden />
                {TRIGGER_LABEL[value]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p id="automation-trigger-hint" className="text-xs text-fg-secondary">
            {hint}
          </p>
        </div>
      </div>
    </StepCard>
  );
}
