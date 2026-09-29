import { describe, expect, it } from "vitest";

import { automation } from "@/test/api";

import { addKeywords, normalizeKeyword, splitKeywords } from "./keywords";
import {
  actionBadge,
  etaText,
  lastRunText,
  overlapText,
  queueBadge,
  queueBanner,
  repliedShare,
  runMarkers,
  settingsSummary,
  statusText,
  triggerSummary,
} from "./format";

const TZ = "Asia/Kolkata";

describe("row labels (UX-SCR-02)", () => {
  it("describes the trigger", () => {
    expect(triggerSummary(automation({ trigger: "dm_keyword" }))).toBe("DM keyword");
    expect(
      triggerSummary(automation({ post_scope: "selected", posts: [{ media_item_id: "1" }, { media_item_id: "2" }, { media_item_id: "3" }] })),
    ).toBe("Comment on 3 posts");
    expect(triggerSummary(automation({ trigger: "comment_any", post_scope: "next_post" }))).toBe("Any comment on next post");
    expect(triggerSummary(automation({ trigger: null }))).toBe("No trigger yet");
  });

  it("names the action", () => {
    expect(actionBadge(automation())).toBe("Message + link");
    expect(actionBadge(automation({ message_buttons: [] }))).toBe("Message");
    expect(actionBadge(automation({ action: "ai_reply" }))).toBe("AI reply");
    expect(actionBadge(automation({ action: null }))).toBeNull();
  });

  it("shows the queue with its ETA", () => {
    expect(queueBadge({ waiting: 2140, eta_minutes: 171 })).toBe("2,140 waiting · about 3 h");
    expect(queueBadge({ waiting: 12, eta_minutes: 1 })).toBe("12 waiting · about 1 min");
    expect(queueBadge({ waiting: 0, eta_minutes: null })).toBeNull();
    expect(queueBanner({ waiting: 2140, eta_minutes: 171 })).toBe("2,140 DMs waiting · all sent in about 3 h");
    expect(etaText(0)).toBe("under a minute");
  });

  it("says when a scheduled automation starts and when one ended", () => {
    expect(statusText(automation({ display_status: "scheduled", starts_at: "2026-10-01T04:00:00Z" }), TZ)).toBe("Starts 1 Oct");
    expect(statusText(automation({ display_status: "ended", ends_at: "2026-10-15T18:00:00Z" }), TZ)).toBe("Ended 15 Oct");
    expect(statusText(automation({ display_status: "active" }), TZ)).toBeNull();
  });

  it("says when it last ran", () => {
    const now = new Date("2026-09-28T12:00:00Z");
    expect(lastRunText("2026-09-28T11:48:00Z", now)).toBe("12m ago");
    expect(lastRunText("2026-09-28T11:59:50Z", now)).toBe("just now");
    expect(lastRunText(null, now)).toBe("No runs yet");
  });
});

describe("editor copy (UX-SCR-03)", () => {
  it("summarises settings on one line", () => {
    expect(
      settingsSummary(
        { cooldown_hours: 24, surge_order: "oldest_first", starts_at: null, ends_at: "2026-10-15T18:29:00Z", trigger: "comment_keyword" },
        TZ,
        null,
      ),
    ).toBe("Once per person every 24 h · Oldest first when busy · Runs until 15 Oct, 23:59 · Disclosure off");
    expect(
      settingsSummary({ cooldown_hours: 0, surge_order: "oldest_first", starts_at: null, ends_at: null, trigger: "dm_keyword" }, TZ, "Sent automatically"),
    ).toBe("Every time someone matches · No end date · Disclosure on");
  });

  it("names the other automation in an overlap and which runs first (FR-AUT-15)", () => {
    const other = overlapText({ keyword: "price", automation_id: "x", automation_name: "Price list DM", this_runs_first: false });
    expect(`${other.before}${other.name}${other.after}`).toBe("“price” is also used by Price list DM, which runs first.");
    const mine = overlapText({ keyword: "price", automation_id: "x", automation_name: "Price list DM", this_runs_first: true });
    expect(mine.after).toBe(". This automation runs first.");
  });

  it("shows replies as a share of DMs", () => {
    expect(repliedShare(38, 100)).toBe("38%");
    expect(repliedShare(0, 0)).toBe("—");
  });
});

describe("run markers (UX-SCR-12, FR-AUT-21, FR-AUT-22)", () => {
  const now = new Date("2026-09-28T12:00:00Z");

  it("names the tap time, the follow status and the nudge", () => {
    expect(
      runMarkers({ confirmed_at: "2026-09-28T08:35:00Z", follows_business: false, nudge_message_id: "m9" }, TZ, now),
    ).toEqual(["Tapped Today 14:05", "Not following", "Nudged"]);
    expect(runMarkers({ confirmed_at: null, follows_business: true, nudge_message_id: null }, TZ, now)).toEqual([
      "Follower",
    ]);
  });

  it("says nothing while the follow status is unknown", () => {
    expect(runMarkers({ confirmed_at: null, follows_business: null, nudge_message_id: null }, TZ, now)).toEqual([]);
    expect(runMarkers({}, TZ, now)).toEqual([]);
  });
});

describe("keywords (FR-AUT-06)", () => {
  it("normalises like the matcher", () => {
    expect(normalizeKeyword("  PRICE  list ")).toBe("price list");
    expect(normalizeKeyword("ｐｒｉｃｅ")).toBe("price");
  });

  it("splits pasted lists and skips duplicates", () => {
    expect(splitKeywords("link, price;\nDetails\t")).toEqual(["link", "price", "Details"]);
    const result = addKeywords(["link"], ["LINK", "price", "Price "]);
    expect(result.keywords).toEqual(["link", "price"]);
    expect(result.duplicates).toEqual(["LINK", "Price"]);
  });

  it("stops at 50", () => {
    const many = Array.from({ length: 49 }, (_, i) => `k${i}`);
    const result = addKeywords(many, ["a", "b"]);
    expect(result.keywords).toHaveLength(50);
    expect(result.overflow).toEqual(["b"]);
  });
});
