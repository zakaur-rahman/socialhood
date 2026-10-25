import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { account } from "@/test/api";
import { assetInfo } from "@/test/composer-fixtures";

import { extrasUnavailable, InstagramExtras, pruneExtras } from "./InstagramExtras";
import type { Draft } from "./use-post-draft";

const BASE: Draft = {
  targets: [{ social_account_id: "a1", caption_override: null }],
  asset_ids: ["as1"],
  caption: "",
  first_comment: null,
  publish_at: null,
  kind: "post",
  collaborators: [],
  location: null,
  user_tags: [],
  cover_asset_id: null,
  cover_offset_ms: null,
  share_to_feed: true,
  audio_name: null,
};

function Harness({
  start = BASE,
  unavailable = null,
  isReel = false,
  onPickCover = () => {},
  onDraft = () => {},
}: {
  start?: Draft;
  unavailable?: string | null;
  isReel?: boolean;
  onPickCover?: (file: File) => void;
  onDraft?: (draft: Draft) => void;
}) {
  const [draft, setDraft] = useState(start);
  return (
    <InstagramExtras
      draft={draft}
      onChange={(patch) => {
        const next = { ...draft, ...patch };
        setDraft(next);
        onDraft(next);
      }}
      unavailable={unavailable}
      isReel={isReel}
      video={assetInfo({ id: "as1", resource_type: "video", duration_s: 20 })}
      coverBusy={false}
      coverNotice={null}
      onPickCover={onPickCover}
      tagTotal={0}
    />
  );
}

describe("InstagramExtras collaborators and location (FR-PUB-07)", () => {
  it("adds collaborators as chips, normalised, up to three", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness onDraft={onDraft} />);
    const field = screen.getByRole("textbox", { name: "Collaborators Add a collaborator" });
    for (const name of ["@Maple.Studio", "bread_fan", "third", "fourth"]) {
      await user.type(field, `${name}{Enter}`);
    }
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ collaborators: ["maple.studio", "bread_fan", "third"] }));
    expect(screen.getByRole("list", { name: "Collaborators" }).children).toHaveLength(3);
  });

  it("names a username Instagram would not accept and does not keep it", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness onDraft={onDraft} />);
    await user.type(screen.getByRole("textbox", { name: "Collaborators Add a collaborator" }), "bad name{Enter}");
    expect(screen.getByText("bad name is not a valid Instagram username.")).toBeInTheDocument();
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ collaborators: [] }));
  });

  it("tells that collaborators cannot be changed after publishing", () => {
    render(<Harness />);
    expect(screen.getByText(/can't change collaborators after publishing/)).toBeInTheDocument();
  });

  it("reads a Page link as the location and explains one it cannot read", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness onDraft={onDraft} />);
    const field = screen.getByRole("textbox", { name: "Location" });
    await user.type(field, "https://www.facebook.com/maplebakery");
    expect(screen.getByText(/Paste the numeric id of a Facebook Page/)).toBeInTheDocument();
    await user.clear(field);
    await user.type(field, "108123456789012");
    expect(screen.getByText("Page id 108123456789012")).toBeInTheDocument();
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ location: "108123456789012" }));
  });

  it("shows the reason instead of the options when they are unavailable", () => {
    const reason = extrasUnavailable({ story: true, kind: "story", hasInstagram: true });
    render(<Harness unavailable={reason} />);
    expect(screen.getByTestId("extras-unavailable")).toHaveTextContent("not available on Stories");
    expect(screen.queryByRole("textbox", { name: "Location" })).toBeNull();
  });
});

describe("extrasUnavailable", () => {
  it("is null for an Instagram post and says why for a Story, a Facebook Reel and a Page", () => {
    expect(extrasUnavailable({ story: false, kind: "post", hasInstagram: true })).toBeNull();
    expect(extrasUnavailable({ story: true, kind: "story", hasInstagram: true })).toContain("Stories");
    expect(extrasUnavailable({ story: false, kind: "post", hasInstagram: false })).toContain("Instagram feature");
    expect(extrasUnavailable({ story: false, kind: "reel", hasInstagram: true })).toContain("Instagram feature");
  });
});

describe("InstagramExtras Reel options", () => {
  it("shows no Reel options for a photo post", () => {
    render(<Harness />);
    expect(screen.queryByTestId("reel-options")).toBeNull();
  });

  it("sets the cover frame in milliseconds, feed sharing and the audio name", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness isReel onDraft={onDraft} />);
    expect(screen.getByRole("switch", { name: "Also share to feed" })).toBeChecked();

    await user.type(screen.getByRole("spinbutton"), "2.5");
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ cover_offset_ms: 2500 }));
    await user.click(screen.getByRole("switch", { name: "Also share to feed" }));
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ share_to_feed: false }));
    await user.type(screen.getByRole("textbox", { name: "Audio name" }), "Morning bake");
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ audio_name: "Morning bake" }));
    expect(screen.getByText(/rename a Reel's audio only once/)).toBeInTheDocument();
  });

  it("switching to an uploaded cover drops the frame, and picking a file hands it over", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    const onPickCover = vi.fn();
    render(<Harness isReel start={{ ...BASE, cover_offset_ms: 1000 }} onDraft={onDraft} onPickCover={onPickCover} />);
    await user.click(screen.getByRole("radio", { name: "Upload an image" }));
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ cover_offset_ms: null }));
    const file = new File(["x"], "cover.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByTestId("composer-cover-input"), file);
    expect(onPickCover).toHaveBeenCalledWith(file);
  });

  it("a cover image wins: choosing a frame again removes it", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness isReel start={{ ...BASE, cover_asset_id: "c1" }} onDraft={onDraft} />);
    await user.click(screen.getByRole("radio", { name: "Frame from the video" }));
    expect(onDraft).toHaveBeenLastCalledWith(expect.objectContaining({ cover_asset_id: null }));
  });
});

describe("pruneExtras", () => {
  const ig = account({ id: "a1", platform: "instagram", capabilities: ["publish"] });
  const page = account({ id: "p1", platform: "facebook", capabilities: ["publish"] });
  const full: Draft = {
    ...BASE,
    collaborators: ["maple.studio"],
    location: "108123456789012",
    user_tags: [{ asset_id: "as1", username: "u", x: 0.1, y: 0.1 }],
    audio_name: "Mix",
    cover_offset_ms: 500,
    share_to_feed: false,
    asset_ids: ["v1"],
  };
  const assets = { v1: assetInfo({ id: "v1", resource_type: "video" }), as1: assetInfo() };

  it("changes nothing before the accounts load or while the options apply", () => {
    expect(pruneExtras(full, [], assets)).toEqual({});
    expect(pruneExtras(full, [ig], assets)).toEqual({});
  });

  it("drops everything for a Story and for a post to a Page only", () => {
    const story = pruneExtras({ ...full, kind: "story" }, [ig], assets);
    expect(story).toMatchObject({ collaborators: [], location: null, user_tags: [], audio_name: null, cover_offset_ms: null, share_to_feed: true });
    const pageOnly = pruneExtras({ ...full, targets: [{ social_account_id: "p1", caption_override: null }] }, [ig, page], assets);
    expect(pageOnly).toMatchObject({ collaborators: [], location: null, user_tags: [], audio_name: null });
  });

  it("drops only the Reel options when the post stops being one video", () => {
    const patch = pruneExtras({ ...full, asset_ids: ["as1"] }, [ig], assets);
    expect(patch).toMatchObject({ audio_name: null, cover_offset_ms: null, share_to_feed: true });
    expect(patch).not.toHaveProperty("collaborators");
    expect(patch).not.toHaveProperty("location");
  });
});
