"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { STORY_LIFETIME_HOURS, STORY_VIDEO_MAX_SECONDS, STORY_VIDEO_MIN_SECONDS } from "@/lib/publishing/rules";

import { Section } from "./Section";

export const POST_TYPE_ID = "composer-type";

export type PostKind = "post" | "story";

/**
 * UX-SCR-13 Type (GR-39): a post, or an Instagram Story. A Story is one photo or video shown
 * full screen for 24 hours; it has no caption, so the caption and first comment are hidden while
 * it is chosen (what was typed is kept, and comes back with Post).
 */
export function PostTypeSection({
  value,
  onChange,
  disabled,
  storyBlockedBy,
}: {
  value: PostKind;
  onChange: (kind: PostKind) => void;
  disabled?: boolean;
  /** GR-30: the name of a chosen account that can't publish Stories (a Facebook Page), if any. */
  storyBlockedBy?: string | null;
}) {
  return (
    <Section id={POST_TYPE_ID} title="Type">
      <ToggleGroup
        aria-label="Post type"
        value={value}
        disabled={disabled}
        onValueChange={(next) => onChange(next as PostKind)}
      >
        <ToggleGroupItem value="post">Post</ToggleGroupItem>
        <ToggleGroupItem value="story" disabled={Boolean(storyBlockedBy) && value !== "story"}>
          Story
        </ToggleGroupItem>
      </ToggleGroup>
      {storyBlockedBy ? (
        <p className="mt-3 text-sm text-fg-secondary" data-testid="story-blocked">
          {storyBlockedBy} is a Facebook Page, and Pages can&apos;t publish Stories from Social Hood yet.
        </p>
      ) : null}
      {value === "story" ? (
        <p className="mt-3 text-sm text-fg-secondary" data-testid="story-hint">
          One photo, or one video of {STORY_VIDEO_MIN_SECONDS} to {STORY_VIDEO_MAX_SECONDS} seconds. 9:16 fits best. Stories have no
          caption and disappear after {STORY_LIFETIME_HOURS} hours.
        </p>
      ) : null}
    </Section>
  );
}
