import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { scheduledPost } from "@/test/schedule";

import {
  bulkResultMessage,
  canMove,
  captionLine,
  lockedMessage,
  moveErrorMessage,
  needsComposer,
  parseHashtags,
  postFormatLabel,
  summarizeSlots,
} from "./format";

function validation(fields: { field: string; message: string }[]) {
  return new ApiError({ type: "about:blank", title: "validation_error", status: 422, code: "validation_error", errors: fields });
}

describe("schedule format", () => {
  it("lets drafts and scheduled posts move, never publishing or published ones (FR-PUB-08)", () => {
    expect(canMove({ status: "scheduled" })).toBe(true);
    expect(canMove({ status: "draft" })).toBe(true);
    for (const status of ["publishing", "published", "partially_published", "failed", "canceled"] as const) {
      expect(canMove({ status })).toBe(false);
    }
    expect(lockedMessage({ status: "published" })).toBe("Published posts can't be moved.");
    expect(lockedMessage({ status: "publishing" })).toBe("Publishing started, so this post can't be moved.");
  });

  it("shows the caption's first line", () => {
    expect(captionLine("\nNew linen\nSecond line")).toBe("New linen");
    expect(captionLine("")).toBe("No caption yet");
  });

  it("names the format", () => {
    expect(postFormatLabel(scheduledPost({ format: "carousel", asset_count: 4 }))).toBe("Carousel · 4 items");
    expect(postFormatLabel(scheduledPost({ format: "reel" }))).toBe("Reel");
    expect(postFormatLabel(scheduledPost({ format: null, asset_count: 0 }))).toBe("No media yet");
  });

  it("summarizes weekly posting times", () => {
    expect(summarizeSlots([])).toBe("None yet");
    expect(
      summarizeSlots([
        { weekday: 0, local_time: "18:00:00" },
        { weekday: 2, local_time: "18:00:00" },
        { weekday: 4, local_time: "18:00:00" },
      ]),
    ).toBe("Mon, Wed, Fri 18:00");
    expect(
      summarizeSlots([
        ...Array.from({ length: 7 }, (_, weekday) => ({ weekday, local_time: "09:00:00" })),
        { weekday: 5, local_time: "18:30:00" },
      ]),
    ).toBe("Every day 09:00 · Sat 18:30");
  });

  it("reads hashtags as typed and keeps them lowercase without # (FR-PUB-12)", () => {
    expect(parseHashtags("#Linen, summer\n#linen  #Slow_Fashion")).toEqual({
      tags: ["linen", "summer", "slow_fashion"],
      invalid: [],
    });
    expect(parseHashtags("#ok #not-ok").invalid).toEqual(["#not-ok"]);
    expect(parseHashtags("#हिंदी").tags).toEqual(["हिंदी"]);
  });

  it("says why a move was refused, in the field's words", () => {
    expect(moveErrorMessage(validation([{ field: "publish_at", message: "Pick a time at least 5 minutes from now." }]))).toBe(
      "Pick a time at least 5 minutes from now.",
    );
    expect(
      moveErrorMessage(new ApiError({ type: "about:blank", title: "conflict", status: 409, code: "conflict", detail: "Publishing started" })),
    ).toBe("Publishing started");
  });

  it("opens the composer only when the post itself needs work", () => {
    expect(needsComposer(validation([{ field: "publish_at", message: "Too soon" }]))).toBe(false);
    expect(needsComposer(validation([{ field: "caption", message: "Too long" }]))).toBe(true);
    expect(needsComposer(validation([{ field: "targets.0", message: "No posting times" }]), ["publish_at", "targets"])).toBe(false);
    expect(needsComposer(new Error("network"))).toBe(false);
  });

  it("reports bulk results with what was skipped (FR-PUB-14)", () => {
    const post = scheduledPost();
    expect(bulkResultMessage("shift", { updated: [post], deleted_ids: [], skipped: [] })).toEqual({
      message: "1 post moved.",
      skipped: null,
    });
    expect(
      bulkResultMessage("delete", {
        updated: [],
        deleted_ids: ["a", "b"],
        skipped: [{ id: "c", code: "conflict", message: "Publishing started." }],
      }),
    ).toEqual({ message: "2 posts deleted.", skipped: "1 post skipped. Publishing started." });
  });
});
