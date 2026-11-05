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
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { CardInset } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { AutomationDefinition, SocialAccount, TriggerName } from "@/lib/api/types";
import { accountLabel } from "@/lib/automations/accounts";
import { errorsFor, triggerPatch, type FieldErrors } from "@/lib/automations/definition";
import { triggerLabel } from "@/lib/automations/format";

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

/** What a Facebook Page has no trigger for (Messenger has no stories), and why (GR-29). */
const FACEBOOK_UNAVAILABLE: Partial<Record<TriggerName, string>> = {
  story_reply: "Facebook Pages have no story replies.",
  story_mention: "Facebook Pages have no story mentions.",
};

/** The trigger's hint, said for the account's platform. */
function hintFor(trigger: TriggerName | null | undefined, platform: string | undefined): string {
  if (!trigger) return "Choose what starts this automation.";
  const base = TRIGGERS.find((item) => item.value === trigger)?.hint ?? "Choose what starts this automation.";
  if (platform !== "facebook") return base;
  const unavailable = FACEBOOK_UNAVAILABLE[trigger];
  if (unavailable) return `${unavailable} Choose another trigger.`;
  if (trigger === "ad_click") return "Someone opens a chat from a Click-to-Messenger ad. Answer any ad, or only the ads you list.";
  if (trigger === "entry_link") {
    return "Someone opens a chat from one of your m.me links or QR codes. Make the links on the Entry links page.";
  }
  return base.replace("Instagram", "Facebook");
}

/** UX-SCR-03 When: the account (an Instagram account or a Facebook Page) and the trigger. */
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
  const chosen = accounts.find((account) => account.id === draft.social_account_id);
  const platform = chosen?.platform;
  const hint = hintFor(draft.trigger, platform);
  const known = Boolean(chosen);

  const setTrigger = (value: TriggerName) => change(triggerPatch(draft, value));

  // A chosen trigger is one row. The list stays open when there is none, when it has a problem, and
  // when the account can't use it, because then the next thing to do is choose another.
  const current = TRIGGERS.find((item) => item.value === draft.trigger);
  const [picking, setPicking] = useState(false);
  const unusable = platform === "facebook" && current !== undefined && Boolean(FACEBOOK_UNAVAILABLE[current.value]);
  const listOpen = picking || !current || Boolean(triggerError) || unusable;

  // The control that had focus goes away on each switch, so focus moves to the one that replaces it.
  const triggerArea = useRef<HTMLDivElement>(null);
  const moveFocus = useRef(false);
  useEffect(() => {
    if (!moveFocus.current) return;
    moveFocus.current = false;
    triggerArea.current?.querySelector<HTMLElement>("[role=radio][data-state=on], [data-trigger-change]")?.focus();
  }, [listOpen]);
  const showList = (open: boolean) => {
    moveFocus.current = true;
    setPicking(open);
  };

  return (
    <StepCard id="when" label="When" state={state} errors={[accountError, triggerError].filter(Boolean) as string[]}>
      <div className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="automation-account">Account</Label>
          {accounts.length === 0 ? (
            <p className="text-sm text-fg-secondary">
              Connect an Instagram account or a Facebook Page to use automations.{" "}
              {/* Underlined at rest: in a line of text, colour alone doesn't mark a link (WCAG 1.4.1). */}
              <Link
                href={`/w/${slug}/settings/connections` as Route}
                className="text-brand-fg underline underline-offset-4"
              >
                Connect an account
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

        {/* A container: the open list takes two columns only when the step is wide enough for their
            labels. Measured from the step, not the window, because the editor's side panel and the
            sidebar take a share. */}
        <div ref={triggerArea} className="@container space-y-2">
          <p id="automation-trigger-label" className="text-sm font-medium">
            Trigger
          </p>
          {listOpen ? (
            <ToggleGroup
              aria-labelledby="automation-trigger-label"
              aria-describedby="automation-trigger-hint"
              value={draft.trigger ?? ""}
              onValueChange={(value) => {
                setTrigger(value as TriggerName);
                showList(false);
              }}
              className="grid @2xl:grid-cols-2"
            >
              {TRIGGERS.map(({ value, icon: Icon }) => (
                <ToggleGroupItem
                  key={value}
                  value={value}
                  disabled={platform === "facebook" && Boolean(FACEBOOK_UNAVAILABLE[value])}
                  // A single group ignores a click on its chosen item, so this is how to keep it.
                  onClick={() => {
                    if (value === draft.trigger) showList(false);
                  }}
                  className="justify-start"
                >
                  <Icon className="size-4" aria-hidden />
                  {triggerLabel(value, platform)}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          ) : current ? (
            <CardInset
              padding="compact"
              role="group"
              aria-labelledby="automation-trigger-label"
              className="flex items-center gap-2 text-sm font-medium"
            >
              <current.icon className="size-4 shrink-0" aria-hidden />
              <span className="min-w-0 flex-1">{triggerLabel(current.value, platform)}</span>
              <Button
                data-trigger-change
                variant="secondary"
                size="sm"
                aria-label="Change trigger"
                aria-describedby="automation-trigger-hint"
                onClick={() => showList(true)}
              >
                Change
              </Button>
            </CardInset>
          ) : null}
          <p id="automation-trigger-hint" className="text-xs text-fg-secondary">
            {hint}
          </p>
        </div>
      </div>
    </StepCard>
  );
}
