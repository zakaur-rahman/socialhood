"use client";

import { Check, ImageOff } from "lucide-react";
import { useMemo } from "react";

import { CardInset } from "@/components/ui/card";
import { ErrorState } from "@/components/states/ErrorState";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useStories } from "@/lib/api/queries";
import type { AutomationDefinition, Story } from "@/lib/api/types";
import { errorsFor, type FieldErrors } from "@/lib/automations/definition";
import { cn } from "@/lib/utils";

import { StepCard, type StepState } from "../StepCard";

type Scope = "all" | "selected";

const SCOPES: { value: Scope; label: string; hint: string }[] = [
  { value: "all", label: "Any story", hint: "Replies to any of your stories, including new ones." },
  {
    value: "selected",
    label: "Chosen stories",
    hint: "Only replies to the stories you pick below. A story lasts 24 hours, so this stops matching when it expires.",
  },
];

/** Whole hours left, rounded up, as "5 h left"; "Expired" once it has passed. */
export function timeLeft(expiresAt: string, now: Date): string {
  const minutes = Math.ceil((new Date(expiresAt).getTime() - now.getTime()) / 60_000);
  if (minutes <= 0) return "Expired";
  if (minutes < 60) return `${minutes} min left`;
  return `${Math.ceil(minutes / 60)} h left`;
}

/**
 * GR-06, the posts slot of a story reply: any story or chosen live stories from a thumbnail grid
 * (read from Instagram), and the optional heart sent with the reply.
 */
export function StoriesStep({
  wid,
  draft,
  change,
  errors,
  state,
  now,
}: {
  wid: string;
  draft: AutomationDefinition;
  change: (patch: Partial<AutomationDefinition>) => void;
  errors: FieldErrors;
  state: StepState;
  now: Date;
}) {
  const selected = draft.post_scope === "selected";
  const chosen = draft.story_ids ?? [];
  const stepErrors = ["post_scope", "story_ids", "story_heart"].flatMap((field) => errorsFor(errors, field));
  const hint = SCOPES.find((scope) => scope.value === (selected ? "selected" : "all"))?.hint;

  return (
    <StepCard id="posts" label="On these stories" state={state} errors={stepErrors}>
      <div className="space-y-4">
        <div className="space-y-2">
          <ToggleGroup
            aria-label="Which stories"
            aria-describedby="automation-story-scope-hint"
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
          <p id="automation-story-scope-hint" className="text-xs text-fg-secondary">
            {hint}
          </p>
        </div>

        {selected ? (
          draft.social_account_id ? (
            <StoryPicker
              wid={wid}
              accountId={draft.social_account_id}
              chosen={chosen}
              now={now}
              onChange={(ids) => change({ story_ids: ids })}
            />
          ) : (
            <p className="text-sm text-fg-secondary">Choose the account in When to see its stories.</p>
          )
        ) : null}

        <CardInset className="flex items-start justify-between gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="automation-story-heart" className="leading-snug">
              Send a heart to the reply
            </Label>
            <p id="automation-story-heart-note" className="text-xs text-fg-secondary">
              Instagram&apos;s heart goes to the person just before your message.
            </p>
          </div>
          <Switch
            id="automation-story-heart"
            checked={draft.story_heart ?? false}
            onCheckedChange={(checked) => change({ story_heart: checked })}
            aria-describedby="automation-story-heart-note"
            className="mt-0.5"
          />
        </CardInset>
      </div>
    </StepCard>
  );
}

function StoryPicker({
  wid,
  accountId,
  chosen,
  now,
  onChange,
}: {
  wid: string;
  accountId: string;
  chosen: string[];
  now: Date;
  onChange: (ids: string[]) => void;
}) {
  const stories = useStories(wid, accountId);
  const live = useMemo(() => new Set((stories.data ?? []).map((story) => story.id)), [stories.data]);
  // Stories chosen earlier that Instagram no longer lists have expired: say so, and let them go.
  const gone = chosen.filter((id) => stories.isSuccess && !live.has(id));
  const toggle = (id: string) => onChange(chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id]);

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-secondary tabular-nums" aria-live="polite">
        {chosen.length === 1 ? "1 story chosen" : `${chosen.length} stories chosen`}
      </p>
      {stories.isPending ? (
        <div role="status" className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5" aria-busy="true" aria-label="Loading stories">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="aspect-[9/16] rounded-lg" />
          ))}
        </div>
      ) : stories.isError ? (
        <ErrorState size="compact" error={stories.error} onRetry={() => void stories.refetch()} />
      ) : stories.data.length === 0 ? (
        <p className="text-sm text-fg-secondary">
          No live stories. Post a story, then choose it here. Stories last 24 hours.
        </p>
      ) : (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5" aria-label="Live stories">
          {stories.data.map((story) => (
            <li key={story.id}>
              <StoryTile story={story} selected={chosen.includes(story.id)} now={now} onToggle={() => toggle(story.id)} />
            </li>
          ))}
        </ul>
      )}
      {gone.length > 0 ? (
        <ul className="space-y-1" aria-label="Expired stories">
          {gone.map((id) => (
            <li key={id} className="flex items-center justify-between gap-3 text-sm text-fg-secondary">
              <span>A story you chose has expired.</span>
              <button type="button" className="text-brand-fg underline underline-offset-4" onClick={() => toggle(id)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function StoryTile({
  story,
  selected,
  now,
  onToggle,
}: {
  story: Story;
  selected: boolean;
  now: Date;
  onToggle: () => void;
}) {
  const thumbnail = story.thumbnail_url ?? story.media_url ?? null;
  const left = timeLeft(story.expires_at, now);
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className={cn(
        "relative grid aspect-[9/16] w-full place-items-center overflow-hidden rounded-lg border-2 bg-raised",
        selected ? "border-brand" : "border-line hover:border-line-strong",
      )}
    >
      {thumbnail ? (
        // eslint-disable-next-line @next/next/no-img-element -- Instagram CDN thumbnails of any size
        <img src={thumbnail} alt="" loading="lazy" className="size-full object-cover" />
      ) : (
        <ImageOff className="size-5 text-fg-secondary" aria-hidden />
      )}
      <span className="sr-only">Story, {left}</span>
      <span aria-hidden className="absolute inset-x-0 bottom-0 bg-media-chip px-1.5 py-0.5 text-2xs text-on-brand">
        {left}
      </span>
      {selected ? (
        <span aria-hidden className="absolute top-1 right-1 grid size-5 place-items-center rounded-full bg-brand text-on-brand">
          <Check className="size-3.5" />
        </span>
      ) : null}
    </button>
  );
}
