import { ChartLegend } from "@/components/charts/ChartLegend";
import { LineChart } from "@/components/charts/LineChart";
import { MAX_SERIES, seriesStyle } from "@/components/charts/palette";
import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { TrendChip } from "@/components/home/MetricTile";
import { Card, CardTitle } from "@/components/ui/card";
import type { AccountBreakdown as Breakdown, BreakdownMetric, Platform, ReportAccount } from "@/lib/api/types";
import { dayLabel, formatMetric, isIdle, reportTrend, unavailableWords, weekLabel } from "@/lib/reports/format";
import { cn } from "@/lib/utils";
import { CARD_TITLE } from "@/styles/tokens";

/** The insight metrics (the rest of a breakdown's metrics are counts of what happened in the inbox). */
const INSIGHTS = new Set(["reach", "views", "accounts_engaged", "interactions", "followers", "follows", "unfollows"]);

type Row = Breakdown & { color: number };

/**
 * Every connected account side by side (the report for all accounts). Each account has one colour
 * from the chart palette, in the order the API lists the accounts, and keeps it in the legend, the
 * table and the lines, so it never changes with what is on screen. The table has this week's number
 * and its change for every metric (counts, then the account insights) with an account in each
 * column; under it each metric that had activity has the weeks leading up to it, one line per
 * account. Metrics with nothing in all those weeks are one line of words, not a flat chart each. A
 * figure a platform can't give is "Not available" with the reason, never 0. The first six accounts
 * are charted; any more are in the table.
 */
export function AccountBreakdown({ breakdown, accounts }: { breakdown: Breakdown[]; accounts: ReportAccount[] }) {
  if (breakdown.length === 0) return null;
  const order = new Map(accounts.map((a, index) => [a.id, index]));
  const rows: Row[] = breakdown.map((row, index) => ({ ...row, color: order.get(row.account.id) ?? index }));
  const charted = rows.filter((row) => row.color < MAX_SERIES);
  const keys = rows[0].metrics.map((m) => ({ key: m.key, label: m.label, insight: INSIGHTS.has(m.key) }));
  const find = (row: Row, key: string): BreakdownMetric | undefined => row.metrics.find((m) => m.key === key);

  const active: typeof keys = [];
  const idle: typeof keys = [];
  for (const k of keys) {
    const everyone = rows.flatMap((row) => find(row, k.key)?.series ?? []);
    (isIdle("count", everyone) ? idle : active).push(k);
  }

  return (
    <section aria-labelledby="report-by-account" className="space-y-3" data-testid="account-breakdown">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="report-by-account" className={CARD_TITLE}>
          Account by account
        </h2>
        <ChartLegend label="Accounts" items={rows.map((row) => ({ key: row.account.id, label: row.account.name, color: row.color, shape: "box" as const }))} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[32rem] border-collapse text-sm" data-testid="breakdown-table">
          <caption className="sr-only">This week for each account, with the change from the week before</caption>
          <thead>
            <tr className="border-b border-line text-left text-xs text-fg-secondary">
              <th scope="col" className="px-3 py-2 font-medium">
                This week
              </th>
              {rows.map((row) => (
                <th key={row.account.id} scope="col" data-account={row.account.id} className="min-w-32 px-3 py-2 text-right font-medium">
                  <AccountMark account={row.account} color={row.color} className="justify-end" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {keys.map((k, index) => (
              <tr key={k.key} data-metric-row={k.key} className={cn("border-b border-line-subtle last:border-b-0", k.insight && !keys[index - 1]?.insight && "border-t border-line")}>
                <th scope="row" className="px-3 py-2 text-left font-medium text-fg-secondary">
                  {k.label}
                </th>
                {rows.map((row) => {
                  const m = find(row, k.key);
                  return (
                    <td key={row.account.id} data-account={row.account.id} data-cell={k.key} className="px-3 py-2 text-right align-top tabular-nums">
                      {m ? <Cell metric={m} /> : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > charted.length ? (
        <p className="text-xs text-fg-secondary">The charts show the first {MAX_SERIES} accounts; every account is in the table.</p>
      ) : null}

      {active.length > 0 ? (
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {active.map((k) => (
            <li key={k.key} data-breakdown={k.key} className="min-w-0">
              <TrendCard label={k.label} metricKey={k.key} rows={charted} />
            </li>
          ))}
        </ul>
      ) : null}
      {idle.length > 0 ? (
        <p className="text-sm text-fg-secondary" data-testid="breakdown-idle">
          No activity on any account in these weeks: {idle.map((k) => k.label).join(", ")}.
        </p>
      ) : null}
    </section>
  );
}

function AccountMark({ account, color, className }: { account: ReportAccount; color: number; className?: string }) {
  return (
    <span className={cn("flex min-w-0 items-center gap-2", className)}>
      <span aria-hidden className={cn("size-2.5 shrink-0 rounded-sm", seriesStyle(color).bg)} />
      <PlatformGlyph platform={account.platform as Platform} className="size-4 shrink-0" />
      {/* Names come in any script: isolated, so a right-to-left name can't reorder what is beside it. */}
      <span className="min-w-0 truncate">
        <bdi>{account.name}</bdi>
      </span>
    </span>
  );
}

function Cell({ metric }: { metric: BreakdownMetric }) {
  if (metric.value === null || metric.value === undefined) {
    return (
      <span className="text-xs text-fg-secondary" data-testid="not-available">
        {unavailableWords(metric.unavailable)}
      </span>
    );
  }
  const trend = reportTrend({ ...metric, unit: "count" });
  const partial = metric.days_total && metric.days_known !== null && metric.days_known !== undefined && metric.days_known < metric.days_total;
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className="font-semibold">{formatMetric("count", metric.value)}</span>
      {trend ? <TrendChip trend={trend} /> : null}
      {partial ? (
        <span className="text-xs font-normal text-fg-secondary">
          readings on {metric.days_known} of {metric.days_total} days
        </span>
      ) : null}
    </span>
  );
}

function TrendCard({ label, metricKey, rows }: { label: string; metricKey: string; rows: Row[] }) {
  const entries = rows
    .map((row) => ({ row, metric: row.metrics.find((m) => m.key === metricKey) }))
    .filter((e): e is { row: Row; metric: BreakdownMetric } => !!e.metric && e.metric.series.some((p) => p.value !== null && p.value !== undefined));
  const first = entries[0]?.metric.series ?? [];
  return (
    <Card className="h-full space-y-3">
      <CardTitle className="text-sm">{label}</CardTitle>
      <LineChart
        height={120}
        label={`${label} by account, week by week`}
        legend={false}
        beforeLabel="Week before"
        format={(v) => formatMetric("count", v)}
        points={first.map((p) => ({ key: p.week_start, label: dayLabel(p.week_start), title: weekLabel(p.week_start) }))}
        series={entries.map(({ row, metric }) => ({ key: row.account.id, label: row.account.name, color: row.color, values: metric.series.map((p) => p.value) }))}
      />
    </Card>
  );
}
