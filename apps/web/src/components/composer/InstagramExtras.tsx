"use client";

import { ImagePlus, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ChipInput } from "@/components/ui/chip-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { SocialAccount } from "@/lib/api/types";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  AUDIO_NAME_MAX_CHARS,
  COLLABORATORS_MAX,
  INSTAGRAM_USERNAME_MAX_CHARS,
  LOCATION_HELP,
  normalizeUsername,
  parseLocation,
  type AssetInfo,
} from "@/lib/publishing/rules";

import { Section } from "./Section";
import type { Draft } from "./use-post-draft";

export const EXTRAS_ID = "composer-instagram-extras";
export const COLLABORATORS_ID = "composer-collaborators";
export const LOCATION_ID = "composer-location";
export const REEL_OPTIONS_ID = "composer-reel-options";

/** Why the Instagram options are hidden, or null when they show. */
export function extrasUnavailable({ story, kind, hasInstagram }: { story: boolean; kind: Draft["kind"]; hasInstagram: boolean }): string | null {
  if (story) return "Collaborators, tags and locations are not available on Stories.";
  if (kind === "reel" || !hasInstagram) {
    return "Collaborators, tags, locations and Reel options are an Instagram feature. Choose an Instagram account to use them.";
  }
  return null;
}

const NO_REEL_OPTIONS: Partial<Draft> = { cover_asset_id: null, cover_offset_ms: null, share_to_feed: true, audio_name: null };

/**
 * The part of the draft to reset because the options no longer apply (FR-PUB-07): a Story, a post
 * without an Instagram account or a Facebook Reel carries none of them; a post that is not one
 * video carries no Reel options. Empty when nothing needs to change, and before the accounts load.
 */
export function pruneExtras(draft: Draft, accounts: Pick<SocialAccount, "id" | "platform">[], assets: Record<string, AssetInfo>): Partial<Draft> {
  if (accounts.length === 0) return {};
  const instagram =
    draft.targets.length === 0 ||
    draft.targets.some((target) => accounts.find((account) => account.id === target.social_account_id)?.platform === "instagram");
  const patch: Partial<Draft> = {};
  if (draft.kind === "story" || draft.kind === "reel" || !instagram) {
    if (draft.collaborators.length) patch.collaborators = [];
    if (draft.location) patch.location = null;
    if (draft.user_tags.length) patch.user_tags = [];
  }
  const oneVideo = draft.asset_ids.length === 1 && assets[draft.asset_ids[0]]?.resource_type !== "image";
  if (draft.kind !== "post" || !instagram || !oneVideo) {
    for (const [key, value] of Object.entries(NO_REEL_OPTIONS) as [keyof Draft, never][]) {
      if (draft[key] !== value) (patch as Record<string, unknown>)[key] = value;
    }
  }
  return patch;
}

/**
 * UX-SCR-13 Instagram options (FR-PUB-07, C-134): collaborators (a Collab post, up to 3), the
 * location (a Facebook Page's id or link), and for a single video the Reel options: cover, also
 * share to feed, audio name. Tags are placed on the photos in Media. Hidden, with the reason, for
 * Stories and for posts without an Instagram account.
 */
export function InstagramExtras({
  draft,
  onChange,
  unavailable,
  isReel,
  video,
  cover,
  coverBusy,
  coverNotice,
  onPickCover,
  tagTotal,
}: {
  draft: Draft;
  onChange: (patch: Partial<Draft>) => void;
  /** The reason the options can't be used on this post, from ``extrasUnavailable``. */
  unavailable: string | null;
  /** The post is one video for Instagram, so the Reel options apply. */
  isReel: boolean;
  video?: AssetInfo;
  /** The uploaded cover image, once known. */
  cover?: AssetInfo;
  coverBusy: boolean;
  coverNotice: string | null;
  onPickCover: (file: File) => void;
  tagTotal: number;
}) {
  const coverInput = useRef<HTMLInputElement>(null);
  const [rejected, setRejected] = useState<string | null>(null);
  const [locationText, setLocationText] = useState(draft.location ?? "");
  const [pickedUpload, setPickedUpload] = useState(false);

  if (unavailable) {
    return (
      <Section id={EXTRAS_ID} title="Instagram options">
        <p className="text-sm text-fg-secondary" data-testid="extras-unavailable">
          {unavailable}
        </p>
      </Section>
    );
  }

  const parsedLocation = locationText.trim() ? parseLocation(locationText) : null;
  const locationBad = locationText.trim() !== "" && parsedLocation === null;
  const coverMode = draft.cover_asset_id || pickedUpload ? "image" : "frame";
  const duration = video?.duration_s ?? null;

  const setCollaborators = (names: string[]) => {
    const valid: string[] = [];
    let bad: string | null = null;
    for (const raw of names) {
      const name = normalizeUsername(raw);
      if (name) valid.push(name);
      else bad = raw;
    }
    setRejected(bad ? `${bad} is not a valid Instagram username.` : null);
    onChange({ collaborators: valid });
  };

  return (
    <Section id={EXTRAS_ID} title="Instagram options" tabIndex={-1}>
      <div className="space-y-5">
        <div id={COLLABORATORS_ID} tabIndex={-1}>
          <Label htmlFor={`${COLLABORATORS_ID}-input`} className="text-sm font-medium">
            Collaborators
          </Label>
          <p className="mb-2 text-xs text-fg-secondary">
            A Collab post shows on their profile too. They get an invite and must accept it. Up to {COLLABORATORS_MAX}, public professional
            accounts that allow collaborator tags. You can&apos;t change collaborators after publishing.
          </p>
          <ChipInput
            id={`${COLLABORATORS_ID}-input`}
            value={draft.collaborators.map((name) => `@${name}`)}
            onValueChange={setCollaborators}
            inputLabel="Add a collaborator"
            listLabel="Collaborators"
            separator="comma"
            normalize={(item) => normalizeUsername(item) ?? item.toLowerCase()}
            max={COLLABORATORS_MAX}
            maxLength={INSTAGRAM_USERNAME_MAX_CHARS + 1}
            placeholder="@username"
            error={rejected}
          />
        </div>

        <div id={LOCATION_ID} tabIndex={-1}>
          <Label htmlFor={`${LOCATION_ID}-input`} className="text-sm font-medium">
            Location
          </Label>
          <p className="mb-2 text-xs text-fg-secondary">
            Instagram places a post by a Facebook Page that has a location. Paste the Page&apos;s id or link. Searching for places needs a
            Meta review we don&apos;t have yet.
          </p>
          <Input
            id={`${LOCATION_ID}-input`}
            data-focus-target
            value={locationText}
            maxLength={300}
            placeholder="Page id or facebook.com/profile.php?id=…"
            aria-invalid={locationBad || undefined}
            aria-describedby={`${LOCATION_ID}-note`}
            onChange={(event) => {
              setLocationText(event.target.value);
              onChange({ location: event.target.value.trim() ? event.target.value.trim() : null });
            }}
          />
          <p id={`${LOCATION_ID}-note`} className={locationBad ? "mt-1 text-xs text-danger-fg" : "mt-1 text-xs text-fg-secondary"}>
            {locationBad ? LOCATION_HELP : parsedLocation ? `Page id ${parsedLocation}` : "Optional."}
          </p>
        </div>

        {tagTotal > 0 ? (
          <p className="text-xs text-fg-secondary" data-testid="tag-total">
            {tagTotal} {tagTotal === 1 ? "person" : "people"} tagged in your photos.
          </p>
        ) : null}

        {isReel ? (
          <div id={REEL_OPTIONS_ID} tabIndex={-1} className="space-y-4 border-t border-line pt-4" data-testid="reel-options">
            <h3 className="text-sm font-medium">Reel options</h3>

            <div className="space-y-2">
              <Label className="text-sm">Cover</Label>
              <ToggleGroup
                aria-label="Cover"
                value={coverMode}
                onValueChange={(next) => {
                  setPickedUpload(next === "image");
                  if (next === "image") onChange({ cover_offset_ms: null });
                  else onChange({ cover_asset_id: null });
                }}
              >
                <ToggleGroupItem value="frame">Frame from the video</ToggleGroupItem>
                <ToggleGroupItem value="image">Upload an image</ToggleGroupItem>
              </ToggleGroup>
              {coverMode === "frame" ? (
                <div>
                  <Label htmlFor="composer-cover-frame" className="text-xs text-fg-secondary">
                    Seconds from the start{duration != null ? ` (the video runs ${duration.toFixed(1)} s)` : ""}
                  </Label>
                  <Input
                    id="composer-cover-frame"
                    data-focus-target
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step={0.1}
                    className="max-w-32"
                    value={draft.cover_offset_ms == null ? "" : String(draft.cover_offset_ms / 1000)}
                    placeholder="0"
                    onChange={(event) => {
                      const seconds = Number(event.target.value);
                      onChange({
                        cover_offset_ms: event.target.value === "" || !Number.isFinite(seconds) || seconds < 0 ? null : Math.round(seconds * 1000),
                      });
                    }}
                  />
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    ref={coverInput}
                    type="file"
                    accept=".jpg,.jpeg,.png"
                    className="hidden"
                    data-testid="composer-cover-input"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      if (file) onPickCover(file);
                    }}
                  />
                  <Button type="button" variant="secondary" size="sm" data-focus-target loading={coverBusy} onClick={() => coverInput.current?.click()}>
                    <ImagePlus aria-hidden /> {draft.cover_asset_id ? "Replace image" : "Choose an image"}
                  </Button>
                  {cover ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={cover.thumbnail_url ?? cover.url} alt="Cover" className="h-12 w-auto rounded-sm" />
                  ) : null}
                  {draft.cover_asset_id ? (
                    <Button type="button" variant="ghost" size="icon-sm" aria-label="Remove cover image" onClick={() => onChange({ cover_asset_id: null })}>
                      <X className="size-3.5" aria-hidden />
                    </Button>
                  ) : null}
                </div>
              )}
              <p className="text-xs text-fg-secondary">
                A cover image is a JPEG or PNG up to 8 MB; 9:16 fits best, other shapes are cropped to the middle. The image wins over a frame.
              </p>
              {coverNotice ? (
                <p role="alert" className="text-xs text-danger-fg">
                  {coverNotice}
                </p>
              ) : null}
            </div>

            <div className="flex items-center gap-3">
              <Switch
                id="composer-share-to-feed"
                checked={draft.share_to_feed}
                onCheckedChange={(on) => onChange({ share_to_feed: on })}
                aria-label="Also share to feed"
              />
              <div>
                <Label htmlFor="composer-share-to-feed" className="text-sm">
                  Also share to feed
                </Label>
                <p className="text-xs text-fg-secondary">Off keeps the Reel in the Reels tab only. Instagram still decides where it is shown.</p>
              </div>
            </div>

            <div>
              <Label htmlFor="composer-audio-name" className="text-sm">
                Audio name
              </Label>
              <Input
                id="composer-audio-name"
                data-focus-target
                value={draft.audio_name ?? ""}
                maxLength={AUDIO_NAME_MAX_CHARS}
                placeholder="Optional"
                onChange={(event) => onChange({ audio_name: event.target.value ? event.target.value : null })}
              />
              <p className="mt-1 text-xs text-fg-secondary">Instagram lets you rename a Reel&apos;s audio only once, so choose it carefully.</p>
            </div>
          </div>
        ) : null}
      </div>
    </Section>
  );
}
