"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  FACEBOOK_REEL_MAX_SECONDS,
  FACEBOOK_REEL_MIN_SECONDS,
  STORY_LIFETIME_HOURS,
  STORY_VIDEO_MAX_SECONDS,
  STORY_VIDEO_MIN_SECONDS,
} from "@/lib/publishing/rules";

import { Section } from "./Section";

export const POST_TYPE_ID = "composer-type";

export type PostKind = "post" | "story" | "reel";

/**
 * UX-SCR-13 Type (GR-39, C-131): a post, a Story, or (with a Facebook Page chosen) a Reel. A
 * Story is one photo or video shown full screen for 24 hours; it has no caption, so the caption
 * and first comment are hidden while it is chosen (what was typed is kept, and comes back with
 * Post). A Reel publishes a Page's video as a Facebook Reel instead of a normal video; Instagram
 * already publishes every single video as a Reel.
 */
export function PostTypeSection({
  value,
  onChange,
  disabled,
  reelAvailable = false,
  instagramToo = false,
}: {
  value: PostKind;
  onChange: (kind: PostKind) => void;
  disabled?: boolean;
  /** A Facebook Page is among the chosen accounts, so a video can be published as a Reel. */
  reelAvailable?: boolean;
  /** An Instagram account is chosen too (its single video is a Reel either way). */
  instagramToo?: boolean;
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
        {reelAvailable || value === "reel" ? <ToggleGroupItem value="reel">Reel</ToggleGroupItem> : null}
        <ToggleGroupItem value="story">Story</ToggleGroupItem>
      </ToggleGroup>
      {value === "reel" ? (
        <p className="mt-3 text-sm text-fg-secondary" data-testid="reel-hint">
          One video of {FACEBOOK_REEL_MIN_SECONDS} to {FACEBOOK_REEL_MAX_SECONDS} seconds, published to your Facebook Page as a Reel.
          9:16 fits best.{instagramToo ? " Instagram publishes a single video as a Reel already." : ""}
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
