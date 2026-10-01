import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { AXE_TAGS, AXE_WIDTHS, axeDir, metaDir, outDir } from "./options";
import { SCREENS } from "./screens";

/**
 * Global teardown: gathers what the tests left in UI_SHOTS_OUT into
 *
 * - axe.json: every axe result (screen, width, rule, impact, node count, targets), the totals per
 *   rule, and what axe couldn't decide ("needs review": contrast over images, gradients, overlaps);
 * - axe-summary.md: the totals by rule, and a table per screen and width;
 * - shots.json: every screenshot with what it shows, its URL and any loading warning.
 *
 * It reads every file in axe/ and meta/, so a --grep run adds to the results of earlier runs into
 * the same folder (each entry has its time).
 */

type Violation = { id: string; impact: string | null; help: string; nodes: number; targets: string[] };
type AxeEntry = {
  screen: string;
  width: number;
  url: string;
  at: string;
  reducedMotion: boolean;
  violations: Violation[];
  incomplete?: { id: string; nodes: number; reasons?: Record<string, number> }[];
};
type Meta = { screen: string; width: number; at: string };

const ORDER = new Map(SCREENS.map((screen, index) => [screen.name, index]));
const IMPACT = ["critical", "serious", "moderate", "minor"];

function readAll<T extends { screen: string; width: number }>(dir: string): T[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((name) => name.endsWith(".json"))
    .map((name) => JSON.parse(readFileSync(join(dir, name), "utf8")) as T)
    .sort((a, b) => (ORDER.get(a.screen) ?? 999) - (ORDER.get(b.screen) ?? 999) || a.width - b.width);
}

const nodesOf = (items: { nodes: number }[]) => items.reduce((sum, item) => sum + item.nodes, 0);

function cell(entry: AxeEntry | undefined): string {
  if (!entry) return "–";
  const review = nodesOf(entry.incomplete ?? []);
  const note = review ? ` · ${review} to review` : "";
  if (entry.violations.length === 0) return `0${note}`;
  const rules = entry.violations.map((v) => `${v.id} ${v.nodes}`).join(", ");
  return `**${entry.violations.length}** (${nodesOf(entry.violations)} nodes: ${rules})${note}`;
}

export default async function report() {
  let out: string;
  try {
    out = outDir();
  } catch {
    return; // the config already explained it
  }
  const entries = readAll<AxeEntry>(axeDir());
  const metas = readAll<Meta>(metaDir());

  if (metas.length > 0) writeFileSync(join(out, "shots.json"), JSON.stringify(metas, null, 2));
  if (entries.length === 0) return;

  const byRule = new Map<string, { id: string; impact: string | null; help: string; nodes: number; shots: string[] }>();
  const review = new Map<string, { id: string; nodes: number; shots: string[]; reasons: Record<string, number> }>();
  for (const entry of entries) {
    const shot = `${entry.screen}-${entry.width}`;
    for (const v of entry.violations) {
      const rule = byRule.get(v.id) ?? { id: v.id, impact: v.impact, help: v.help, nodes: 0, shots: [] };
      rule.nodes += v.nodes;
      rule.shots.push(shot);
      byRule.set(v.id, rule);
    }
    for (const item of entry.incomplete ?? []) {
      const rule = review.get(item.id) ?? { id: item.id, nodes: 0, shots: [], reasons: {} };
      rule.nodes += item.nodes;
      rule.shots.push(shot);
      for (const [reason, count] of Object.entries(item.reasons ?? {})) rule.reasons[reason] = (rule.reasons[reason] ?? 0) + count;
      review.set(item.id, rule);
    }
  }
  const rules = [...byRule.values()].sort(
    (a, b) => IMPACT.indexOf(a.impact ?? "") - IMPACT.indexOf(b.impact ?? "") || b.nodes - a.nodes,
  );
  const needsReview = [...review.values()].sort((a, b) => b.nodes - a.nodes);
  const totals = {
    shots: entries.length,
    shotsWithViolations: entries.filter((e) => e.violations.length > 0).length,
    violations: entries.reduce((sum, e) => sum + e.violations.length, 0),
    nodes: entries.reduce((sum, e) => sum + nodesOf(e.violations), 0),
    needsReviewNodes: entries.reduce((sum, e) => sum + nodesOf(e.incomplete ?? []), 0),
  };
  writeFileSync(
    join(out, "axe.json"),
    JSON.stringify({ generated: new Date().toISOString(), tags: AXE_TAGS, totals, rules, needsReview, entries }, null, 2),
  );

  const screens = [...new Set(entries.map((e) => e.screen))];
  const widths = AXE_WIDTHS.filter((w) => entries.some((e) => e.width === w));
  const lines = [
    "# axe summary",
    "",
    `Generated ${new Date().toISOString()} from ${entries.length} results in \`axe/\` (tags ${AXE_TAGS.join(", ")}).`,
    `${totals.violations} violations (a rule failing on a screen at a width) on ${totals.shotsWithViolations} of ${totals.shots} screens and widths, ${totals.nodes} nodes; ${totals.needsReviewNodes} nodes axe couldn't decide.`,
    "",
    "## By rule",
    "",
    "| Rule | Impact | Screens × widths | Nodes | What |",
    "|---|---|---:|---:|---|",
    ...rules.map((r) => `| \`${r.id}\` | ${r.impact ?? "–"} | ${r.shots.length} | ${r.nodes} | ${r.help} |`),
    "",
    "Needs review: axe couldn't decide these (contrast over a background image, a gradient or an",
    "overlap); check them by eye or with a contrast tool.",
    "",
    "| Rule | Screens × widths | Nodes | Why (axe's reason: nodes) |",
    "|---|---:|---:|---|",
    ...needsReview.map(
      (r) =>
        `| \`${r.id}\` | ${r.shots.length} | ${r.nodes} | ${Object.entries(r.reasons)
          .sort((a, b) => b[1] - a[1])
          .map(([reason, count]) => `${reason}: ${count}`)
          .join(", ")} |`,
    ),
    "",
    "## By screen",
    "",
    `| Screen | ${widths.map((w) => `${w} px`).join(" | ")} |`,
    `|---|${widths.map(() => "---").join("|")}|`,
    ...screens.map(
      (screen) => `| ${screen} | ${widths.map((w) => cell(entries.find((e) => e.screen === screen && e.width === w))).join(" | ")} |`,
    ),
    "",
  ];
  writeFileSync(join(out, "axe-summary.md"), lines.join("\n"));
  console.log(
    `[ui-shots] axe: ${totals.violations} violations, ${totals.nodes} nodes, ${totals.needsReviewNodes} to review; see ${join(out, "axe-summary.md")}`,
  );
}
