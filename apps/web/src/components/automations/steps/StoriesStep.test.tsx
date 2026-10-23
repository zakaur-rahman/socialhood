import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { toDefinition } from "@/lib/automations/definition";
import type { Story } from "@/lib/api/types";
import { automation, json, renderWithApi } from "@/test/api";

import { StoriesStep, timeLeft } from "./StoriesStep";

const NOW = new Date("2026-10-24T12:00:00Z");

function story(id: string, hoursLeft: number): Story {
  return {
    id,
    thumbnail_url: null,
    media_url: "https://cdn.example/s.jpg",
    permalink: null,
    posted_at: "2026-10-24T08:00:00Z",
    expires_at: new Date(NOW.getTime() + hoursLeft * 3_600_000).toISOString(),
  };
}

function setup(patch: Parameters<typeof automation>[0], stories: Story[] = [story("s1", 5), story("s2", 20)]) {
  const draft = toDefinition(automation({ trigger: "story_reply", keywords: [], ...patch }));
  const change = vi.fn();
  renderWithApi(<StoriesStep wid="w1" draft={draft} change={change} errors={{}} state="incomplete" now={NOW} />, {
    handlers: { "GET /v1/w/:wid/stories": () => json({ items: stories }) },
  });
  return change;
}

describe("StoriesStep (GR-06)", () => {
  it("says how long a story has left", () => {
    expect(timeLeft(story("s", 5).expires_at, NOW)).toBe("5 h left");
    expect(timeLeft(story("s", 0.5).expires_at, NOW)).toBe("30 min left");
    expect(timeLeft(story("s", -1).expires_at, NOW)).toBe("Expired");
  });

  it("answers any story without loading the list", () => {
    setup({ post_scope: "all", social_account_id: "a1" });
    expect(screen.queryByRole("list", { name: "Live stories" })).not.toBeInTheDocument();
  });

  it("picks chosen stories from the live ones", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "selected", social_account_id: "a1" });
    const tile = (await screen.findAllByRole("button", { name: /Story, / }))[0];
    await user.click(tile);
    expect(change).toHaveBeenCalledWith({ story_ids: ["s1"] });
  });

  it("turns the heart on", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "all" });
    await user.click(screen.getByRole("switch", { name: "Send a heart to the reply" }));
    expect(change).toHaveBeenCalledWith({ story_heart: true });
  });

  it("lets a chosen story that has expired go", async () => {
    const user = userEvent.setup();
    const change = setup({ post_scope: "selected", social_account_id: "a1", story_ids: ["gone"] });
    await user.click(await screen.findByRole("button", { name: "Remove" }));
    expect(change).toHaveBeenCalledWith({ story_ids: [] });
  });
});
