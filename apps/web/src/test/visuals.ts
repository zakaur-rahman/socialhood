/**
 * Fixtures for the VIS-07 to VIS-12 visuals (trend, lead list, table), shaped like the API's, with
 * figures a person can check by eye. The GR-38 ones live in ./agent.
 */
import type { LeadListVisual, LeadRow, TableVisual, TrendPoint, TrendVisual } from "@/lib/api/types";

export function trendPoint(day: number, value: number | null, daysKnown = 1): TrendPoint {
  return { day: `2026-10-${String(day).padStart(2, "0")}`, value, days_known: value === null ? 0 : daysKnown };
}

export function trendVisual(overrides: Partial<TrendVisual> = {}): TrendVisual {
  const points = [trendPoint(1, 100), trendPoint(2, 120), trendPoint(3, null), trendPoint(4, 90), trendPoint(5, 150)];
  return {
    kind: "trend",
    version: 1,
    title: "Reach, 1-5 Oct 2026: @maple.bakery",
    metric_key: "reach",
    metric_label: "Reach",
    format: "count",
    granularity: "day",
    period: { start: "2026-10-01", end: "2026-10-05", label: "1-5 Oct 2026", days: 5 },
    account_label: "@maple.bakery",
    points,
    known_points: 4,
    first: points[0],
    last: points[4],
    lowest: points[3],
    highest: points[4],
    change_pct: 50,
    direction: "up",
    summary:
      "Reach by day, 1-5 Oct 2026. From 100 on 1 Oct to 150 on 5 Oct (+50.0%). Lowest 90 on 4 Oct, highest 150 on 5 Oct.",
    note: "1 of 5 days have no reading.",
    ...overrides,
  };
}

export function leadRow(overrides: Partial<LeadRow> = {}): LeadRow {
  return {
    contact_id: "c1",
    conversation_id: "cv1",
    name: "Priya Shah",
    platform: "instagram",
    lead_score: 90,
    lead_stage: "new",
    last_activity_label: "2 hours ago",
    ...overrides,
  };
}

export function leadListVisual(overrides: Partial<LeadListVisual> = {}): LeadListVisual {
  return {
    kind: "lead_list",
    version: 1,
    title: "Leads waiting for your reply",
    total: 5,
    items: [
      leadRow(),
      leadRow({ contact_id: "c2", conversation_id: "cv2", name: "Rahul Mehta", lead_score: 60, lead_stage: "qualified", last_activity_label: "yesterday" }),
      leadRow({ contact_id: "c3", conversation_id: null, name: "Ananya Gupta", lead_score: null, last_activity_label: null }),
    ],
    reply_ids: ["cv1", "cv2"],
    more_route: "inbox?view=needs_reply",
    ...overrides,
  };
}

export function tableVisual(overrides: Partial<TableVisual> = {}): TableVisual {
  return {
    kind: "table",
    version: 1,
    title: "Orders",
    columns: [
      { key: "order", label: "Order", align: "left", format: "text" },
      { key: "customer", label: "Customer", align: "left", format: "text" },
      { key: "total", label: "Total", align: "right", format: "text" },
      { key: "score", label: "Score", align: "right", format: "count" },
    ],
    rows: [
      { cells: ["#12", "@priya", "INR 1598.00", 82] },
      { cells: ["#11", null, "INR 799.00", null] },
    ],
    total: 14,
    more_route: "orders",
    ...overrides,
  };
}
