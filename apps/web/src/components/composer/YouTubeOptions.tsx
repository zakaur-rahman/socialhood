"use client";

import { ChevronDown } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ChipInput } from "@/components/ui/chip-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { youtubeCopy } from "@/lib/copy";
import {
  charCount,
  tagsLength,
  YOUTUBE_AI_HELP_URL,
  YOUTUBE_CATEGORIES,
  YOUTUBE_KIDS_HELP_URL,
  YOUTUBE_TAGS_MAX_CHARS,
  YOUTUBE_TITLE_MAX_CHARS,
  type YouTubeOptions as Options,
} from "@/lib/publishing/rules";
import { cn } from "@/lib/utils";

import { Section } from "./Section";

export const YOUTUBE_SECTION_ID = "composer-youtube";
export const YOUTUBE_TITLE_ID = "composer-youtube-title";
export const YOUTUBE_KIDS_ID = "composer-youtube-kids";
export const YOUTUBE_AI_ID = "composer-youtube-ai";
export const YOUTUBE_TAGS_ID = "composer-youtube-tags";

/** The element a YouTube option's checklist item links to (``targets.{i}.options.{name}``). */
export function youtubeFieldId(name: string): string {
  if (name === "made_for_kids") return YOUTUBE_KIDS_ID;
  if (name === "synthetic_media") return YOUTUBE_AI_ID;
  if (name === "tags" || name === "category_id" || name === "notify_subscribers") return YOUTUBE_TAGS_ID;
  if (name === "title") return YOUTUBE_TITLE_ID;
  return YOUTUBE_SECTION_ID;
}

const NO_CATEGORY = "none";

/** A required Yes/No with no default (YouTube's own rule for made for kids; D4). */
function YesNo({
  id,
  legend,
  help,
  value,
  onChange,
}: {
  id: string;
  legend: string;
  help: ReactNode;
  value: boolean | null;
  onChange: (value: boolean) => void;
}) {
  const name = useId();
  return (
    <fieldset id={id} tabIndex={-1} className="space-y-1.5" aria-describedby={`${id}-help`}>
      <legend className="text-sm font-medium">{legend}</legend>
      <p id={`${id}-help`} className="text-xs text-fg-secondary">
        {help}
      </p>
      <div className="flex gap-4" role="radiogroup" aria-required="true">
        {[true, false].map((option) => (
          <label key={String(option)} className="flex min-h-10 items-center gap-2 text-sm">
            <input
              type="radio"
              name={name}
              className="size-4 accent-brand"
              checked={value === option}
              onChange={() => onChange(option)}
              {...(option ? { "data-focus-target": true } : {})}
            />
            {option ? "Yes" : "No"}
          </label>
        ))}
      </div>
      {value === null ? <p className="text-xs text-fg-secondary">Not answered yet.</p> : null}
    </fieldset>
  );
}

/**
 * UX-SCR-13 YouTube (C-195 S-9): shown when a YouTube channel is chosen. Video or Short, the
 * title (required, 100 characters), privacy (Public by default), made for kids and the AI
 * disclosure (both required, neither answered for you), and behind More the category, tags (500
 * characters in total) and whether subscribers are notified. Every YouTube channel of the post
 * gets these. The caption above is the video's description.
 */
export function YouTubeOptions({
  options,
  onChange,
  route,
}: {
  options: Options;
  onChange: (patch: Partial<Options>) => void;
  /** ``direct``: YouTube alone, uploaded from the browser; ``media``: through the media tray with the other platforms. */
  route: "direct" | "media";
}) {
  const [more, setMore] = useState(Boolean(options.category_id || options.tags.length || !options.notify_subscribers));
  const titleChars = charCount(options.title);
  const tagChars = tagsLength(options.tags);

  return (
    <Section id={YOUTUBE_SECTION_ID} title="YouTube" tabIndex={-1}>
      <div className="space-y-5">
        <p className="text-xs text-fg-secondary" data-testid="youtube-route">
          {route === "direct" ? youtubeCopy.directRoute : youtubeCopy.mediaRoute}
        </p>

        <div className="space-y-2">
          <Label className="text-sm font-medium">Type</Label>
          <ToggleGroup aria-label="YouTube type" value={options.format} onValueChange={(format) => onChange({ format: format as Options["format"] })}>
            <ToggleGroupItem value="video">Video</ToggleGroupItem>
            <ToggleGroupItem value="short">Short</ToggleGroupItem>
          </ToggleGroup>
          {options.format === "short" ? <p className="text-xs text-fg-secondary">{youtubeCopy.shortHint}</p> : null}
        </div>

        <div className="space-y-1">
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor={`${YOUTUBE_TITLE_ID}-input`} className="text-sm font-medium">
              Title
            </Label>
            <span className={cn("text-xs tabular-nums", titleChars > YOUTUBE_TITLE_MAX_CHARS ? "text-danger-fg" : "text-fg-secondary")}>
              {titleChars}/{YOUTUBE_TITLE_MAX_CHARS}
            </span>
          </div>
          <div id={YOUTUBE_TITLE_ID} tabIndex={-1}>
            <Input
              id={`${YOUTUBE_TITLE_ID}-input`}
              data-focus-target
              required
              value={options.title}
              placeholder="What's the video called?"
              aria-invalid={titleChars > YOUTUBE_TITLE_MAX_CHARS || /[<>]/.test(options.title) || undefined}
              onChange={(event) => onChange({ title: event.target.value })}
            />
          </div>
          {/[<>]/.test(options.title) ? <p className="text-xs text-danger-fg">YouTube titles can&apos;t contain &lt; or &gt;.</p> : null}
        </div>

        <div className="space-y-2">
          <Label className="text-sm font-medium">Privacy</Label>
          <ToggleGroup aria-label="Privacy" value={options.privacy} onValueChange={(privacy) => onChange({ privacy: privacy as Options["privacy"] })}>
            <ToggleGroupItem value="public">Public</ToggleGroupItem>
            <ToggleGroupItem value="unlisted">Unlisted</ToggleGroupItem>
            <ToggleGroupItem value="private">Private</ToggleGroupItem>
          </ToggleGroup>
          <p className="text-xs text-fg-secondary">
            {options.privacy === "public"
              ? "Anyone can find and watch it once it goes live."
              : options.privacy === "unlisted"
                ? "Only people with the link can watch it."
                : "Only you and people you choose can watch it."}
          </p>
        </div>

        <YesNo
          id={YOUTUBE_KIDS_ID}
          legend="Is this video made for kids?"
          value={options.made_for_kids}
          onChange={(made_for_kids) => onChange({ made_for_kids })}
          help={
            <>
              {youtubeCopy.kidsHelp}{" "}
              <a href={YOUTUBE_KIDS_HELP_URL} target="_blank" rel="noopener noreferrer" className="text-brand-fg underline-offset-4 hover:underline">
                YouTube&apos;s guide<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </>
          }
        />

        <YesNo
          id={YOUTUBE_AI_ID}
          legend="Does it contain realistic AI-made or altered content?"
          value={options.synthetic_media}
          onChange={(synthetic_media) => onChange({ synthetic_media })}
          help={
            <>
              {youtubeCopy.aiHelp}{" "}
              <a href={YOUTUBE_AI_HELP_URL} target="_blank" rel="noopener noreferrer" className="text-brand-fg underline-offset-4 hover:underline">
                Learn more<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </>
          }
        />

        <div className="border-t border-line pt-3">
          <Button type="button" variant="ghost" size="sm" aria-expanded={more} aria-controls={YOUTUBE_TAGS_ID} onClick={() => setMore(!more)}>
            <ChevronDown className={cn("transition-transform duration-fast ease-standard", more && "rotate-180")} aria-hidden /> More
          </Button>
          <div id={YOUTUBE_TAGS_ID} tabIndex={-1} hidden={!more} className="mt-3 space-y-4">
            <div className="space-y-1">
              <Label htmlFor="composer-youtube-category" className="text-sm">
                Category
              </Label>
              <Select
                value={options.category_id ?? NO_CATEGORY}
                onValueChange={(value) => onChange({ category_id: value === NO_CATEGORY ? null : value })}
              >
                <SelectTrigger id="composer-youtube-category" size="lg" className="w-full max-w-72">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_CATEGORY}>Channel default</SelectItem>
                  {YOUTUBE_CATEGORIES.map((category) => (
                    <SelectItem key={category.id} value={category.id}>
                      {category.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="composer-youtube-tags-input" className="text-sm">
                  Tags
                </Label>
                <span className={cn("text-xs tabular-nums", tagChars > YOUTUBE_TAGS_MAX_CHARS ? "text-danger-fg" : "text-fg-secondary")}>
                  {tagChars}/{YOUTUBE_TAGS_MAX_CHARS}
                </span>
              </div>
              <ChipInput
                id="composer-youtube-tags-input"
                value={options.tags}
                onValueChange={(tags) => onChange({ tags })}
                inputLabel="Add a tag"
                listLabel="Tags"
                separator="comma"
                placeholder="Optional"
              />
              <p className="text-xs text-fg-secondary">Tags help with misspelled searches. Titles and descriptions matter more.</p>
            </div>
            <div className="flex items-center gap-3">
              <Switch
                id="composer-youtube-notify"
                checked={options.notify_subscribers}
                onCheckedChange={(notify_subscribers) => onChange({ notify_subscribers })}
              />
              <Label htmlFor="composer-youtube-notify" className="text-sm">
                Notify subscribers
              </Label>
            </div>
          </div>
        </div>
      </div>
    </Section>
  );
}
