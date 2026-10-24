import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { MATRIX, NOT_SHOWN, PLAN_TABLE_KEYS, TRIAL_DAYS, rowCell, type PlanKey } from "./plan-matrix";
import table from "./plan-table.json";
import { FALLBACK_ENTITLEMENTS } from "./plans";

const PLANS: PlanKey[] = ["free", "pro", "max"];
const rows = MATRIX.flatMap((group) => group.rows);
const row = (key: string) => {
  const found = rows.find((entry) => entry.key === key);
  if (!found) throw new Error(`no row for ${key}`);
  return found;
};
const cells = (key: string) => PLANS.map((plan) => rowCell(row(key), plan));

describe("the pricing page's plan table (GR-37)", () => {
  it("shows every entitlement billing/plans.py has, or leaves it out on purpose", () => {
    const shown = new Set(rows.map((entry) => entry.key));
    const missing = PLAN_TABLE_KEYS.filter((key) => !shown.has(key) && !NOT_SHOWN.includes(key));
    expect(missing).toEqual([]);
    expect(rows.length).toBe(shown.size);
  });

  it("is the file the API's unit test checks against plans.py: three plans and the trial", () => {
    expect(table.plans).toEqual(["free", "pro", "max"]);
    expect(TRIAL_DAYS).toEqual({ free: 0, pro: 7, max: 0 });
    // The landing page's offline fallback reads the same file, so it can't drift either.
    expect(FALLBACK_ENTITLEMENTS.pro.find((entry) => entry.key === "members")?.value).toBe(table.entitlements.members.pro);
  });

  it("words the owner's decisions: seats (PD-1), broadcasts (PD-4), API and Sheets (PD-6), widget (PD-7), commerce (PD-8)", () => {
    expect(cells("members")).toEqual(["1", "3", "10"]);
    expect(cells("broadcast_recipients_monthly")).toEqual(["Not included", "2,500", "25,000"]);
    expect(cells("public_api")).toEqual(["Not included", "Included", "Included"]);
    expect(cells("sheets_sync")).toEqual(["Not included", "Included", "Included"]);
    expect(cells("widget_remove_branding")).toEqual(["Not included", "Included", "Included"]);
    expect(cells("commerce")).toEqual(["Not included", "Included", "Included"]);
    expect(rowCell(row("catalogue_products"), "free")).toBe("Not included");
  });

  it("reads unlimited, days, modes and analysed posts in plain words", () => {
    expect(rowCell(row("active_automations"), "max")).toBe("Unlimited");
    expect(cells("message_history_days")).toEqual(["90 days", "Unlimited", "Unlimited"]);
    expect(cells("ai_modes")).toEqual(["Off, Suggest", "Off, Suggest, Auto", "Off, Suggest, Auto"]);
    expect(cells("comment_intelligence_posts")).toEqual(["Latest 5", "All posts", "All posts"]);
  });

  it("marks the conditional rows honestly", () => {
    expect(row("broadcast_recipients_monthly").note).toMatch(/Coming soon/);
    expect(row("commerce").note).toMatch(/Shopify sync arrives/);
  });

  it("types no limit into the module: counts come from the JSON", () => {
    const source = readFileSync(join(__dirname, "plan-matrix.ts"), "utf8");
    expect(source).not.toMatch(/\b(2500|25000|5000000|200000)\b/);
  });
});
