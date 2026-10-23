"use client";

import {
  AtSign,
  Hand,
  Link2,
  ListChecks,
  Megaphone,
  MessageCircle,
  MessagesSquare,
  MessageSquareReply,
  Reply,
  Send,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition, SocialAccount, TriggerName } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { errorsFor, triggerPatch, type FieldErrors } from "@/lib/automations/definition";
import { TRIGGER_LABEL_IG } from "@/lib/automations/format";

import { StepCard, type StepState } from "../StepCard";

const TRIGGERS: { value: TriggerName; icon: typeof Send; hint: string }[] = [
  { value: "comment_keyword", icon: MessageCircle, hint: "Someone comments one of your keywords on a post." },
  { value: "comment_any", icon: MessagesSquare, hint: "Anyone comments on the posts you choose." },
  { value: "dm_keyword", icon: Send, hint: "Someone sends a DM with one of your keywords." },
  { value: "story_reply", icon: Reply, hint: "Someone replies to one of your stories. Add keywords, or answer every reply." },
  { value: "story_mention", icon: AtSign, hint: "Someone mentions you in their story. Thank them or send a reward." },
  { value: "entry_link", icon: Link2, hint: "Someone opens a chat from one of your entry links or QR codes. Make the links on the Entry links page." },
  { value: "ad_click", icon: Megaphone, hint: "Someone opens a chat from an Instagram ad. Answer any ad, or only the ads you list." },
  {
    value: "ice_breaker",
    icon: ListChecks,
    hint: "Someone taps one of your conversation starters. Set the starters up under Conversation starters on the Automations page.",
  },
  {
    value: "first_message",
    icon: Hand,
    hint: "A welcome: it goes to someone the first time they DM this account, whatever they write. It runs only when no other automation answers that message.",
  },
  {
    value: "default_reply",
    icon: MessageSquareReply,
    hint: "A catch-all: it answers a DM that no other automation matched, but only while AI replies are Off for the conversation. With AI on Suggest or Auto, the AI answers instead.",
  },
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

  const setTrigger = (value: TriggerName) => change(triggerPatch(draft, value));

  return (
    <StepCard id="when" label="When" state={state} errors={[accountError, triggerError].filter(Boolean) as string[]}>
      <div className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="automation-account">Instagram account</Label>
          {accounts.length === 0 ? (
            <p className="text-sm text-fg-secondary">
              Connect an Instagram account to use automations.{" "}
              {/* Underlined at rest: in a line of text, colour alone doesn't mark a link (WCAG 1.4.1). */}
              <Link
                href={`/w/${slug}/settings/connections` as Route}
                className="text-brand-fg underline underline-offset-4"
              >
                Connect Instagram
              </Link>
            </p>
          ) : (
            <Select
              value={draft.social_account_id ?? ""}
              onValueChange={(value) =>
                // Posts and stories belong to one account, so a new account starts with none chosen.
                change({ social_account_id: value, media_item_ids: [], scheduled_post_ids: [], story_ids: [] })
              }
            >
              <SelectTrigger
                id="automation-account"
                size="lg"
                className="min-w-56"
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

        {/* A container: the triggers sit in a row only when the step is wide enough for their
            labels (about 640 px, "Instagram comment keyword" …); narrower, they stack, and five
            wrap onto a second row. Measured from
            the step, not the window, because the editor's side panel and the sidebar take a share. */}
        <div className="@container space-y-2">
          <p id="automation-trigger-label" className="text-sm font-medium">
            Trigger
          </p>
          <ToggleGroup
            aria-labelledby="automation-trigger-label"
            aria-describedby="automation-trigger-hint"
            value={draft.trigger ?? ""}
            onValueChange={(value) => setTrigger(value as TriggerName)}
            className="flex-col @2xl:flex-row @2xl:flex-wrap"
          >
            {TRIGGERS.map(({ value, icon: Icon }) => (
              <ToggleGroupItem key={value} value={value}>
                <Icon className="size-4" aria-hidden />
                {TRIGGER_LABEL_IG[value]}
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
