/**
 * Schedule page fixtures (P7). Times are chosen in Asia/Kolkata (UTC+5:30): "now" is Tuesday
 * 29 September 2026, 10:00, so the week shown is Monday 28 September to Sunday 4 October.
 */
import type {
  Calendar,
  CalendarMessage,
  HashtagGroup,
  PostingSlots,
  ScheduledPostDetail,
  ScheduledPostSummary,
} from "@/lib/api/types";

export const NOW = new Date("2026-09-29T04:30:00Z"); // Tue 29 Sep 10:00 IST

/** An instant from a wall-clock time in Kolkata: ist("2026-09-30", "18:00"). */
export function ist(date: string, time: string): string {
  return new Date(`${date}T${time}:00+05:30`).toISOString();
}

let seq = 0;

export function scheduledPost(overrides: Partial<ScheduledPostSummary> = {}): ScheduledPostSummary {
  seq += 1;
  return {
    id: `sp${seq}`,
    status: "scheduled",
    format: "image",
    caption: "Linen styles for the weekend",
    publish_at: ist("2026-09-29", "12:00"),
    published_at: null,
    thumbnail_url: null,
    asset_count: 1,
    targets: [{ social_account_id: "a1", status: "pending" }],
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    ...overrides,
  };
}

/** The API's answer to a lifecycle call: the summary plus the composer's fields. */
export function detail(post: ScheduledPostSummary, overrides: Partial<ScheduledPostDetail> = {}): ScheduledPostDetail {
  return { ...post, first_comment: null, assets: [], automations: [], checklist: [], ready: true, ...overrides };
}

export function calendarMessage(overrides: Partial<CalendarMessage> = {}): CalendarMessage {
  seq += 1;
  return {
    id: `dm${seq}`,
    conversation_id: "c1",
    social_account_id: "a1",
    text: "Your order ships tomorrow",
    attachment_asset_ids: [],
    send_at: ist("2026-10-01", "21:00"),
    status: "scheduled",
    contact: { display_name: "Priya Nair" },
    platform: "instagram",
    ...overrides,
  };
}

export function calendar(overrides: Partial<Calendar> = {}): Calendar {
  return {
    timezone: "Asia/Kolkata",
    start: "2026-09-28",
    end: "2026-10-04",
    posts: [],
    messages: [],
    slots: [],
    accounts: [
      { social_account_id: "a1", published_24h: 1, publishing_limit: 50, next_free_at: ist("2026-09-30", "18:00") },
    ],
    ...overrides,
  };
}

export function postingSlots(overrides: Partial<PostingSlots> = {}): PostingSlots {
  return {
    social_account_id: "a1",
    timezone: "Asia/Kolkata",
    slots: [
      { weekday: 0, local_time: "18:00:00" },
      { weekday: 2, local_time: "18:00:00" },
      { weekday: 4, local_time: "18:00:00" },
    ],
    next_free_at: [ist("2026-09-30", "18:00"), ist("2026-10-02", "18:00"), ist("2026-10-05", "18:00")],
    ...overrides,
  };
}

export function hashtagGroup(overrides: Partial<HashtagGroup> = {}): HashtagGroup {
  seq += 1;
  return {
    id: `hg${seq}`,
    name: "Summer linen",
    hashtags: ["linen", "summerstyle", "handmade", "slowfashion", "madeinindia"],
    created_at: "2026-09-20T10:00:00Z",
    updated_at: "2026-09-20T10:00:00Z",
    ...overrides,
  };
}
