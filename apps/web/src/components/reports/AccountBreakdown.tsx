import { BarChart, type BarRow } from "@/components/charts/BarChart";
import { ChartLegend } from "@/components/charts/ChartLegend";
import { LineChart } from "@/components/charts/LineChart";
import { MAX_SERIES, seriesStyle } from "@/components/charts/palette";
import { PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { TrendChip } from "@/components/home/MetricTile";
import { Card, CardTitle } from "@/components/ui/card";
import type { AccountBreakdown as Breakdown, BreakdownMetric, Platform, ReportAccount } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { changeText, dayLabel, formatMetric, reportTrend, unavailableWords, weekLabel } from "@/lib/reports/format";
import { CARD_TITLE } from "@/styles/tokens";

/**
 * Every connected account side by side (the report for all accounts). Each account has one colour
 * from the chart palette, in the order the API lists the accounts, and keeps it in the legend, the
 * table, the bars and the lines, so it never changes with what is on screen. A table has the
 * numbers; under it each count has this week against last week (bars) and the weeks leading up
 * to it (one line per account). A figure a platform can't give is "Not available" with the reason,
 * never 0. The first six accounts are charted; any more are in the table.
 */
export function AccountBreakdown({ breakdown, accounts }: { breakdown: Breakdown[]; accounts: ReportAccount[] }) {
  if (breakdown.length === 0) return null;
  const order = new Map(accounts.map((a, index) => [a.id, index]));
  const rows = breakdown.map((row, index) => ({ ...row, color: order.get(row.account.id) ?? index }));
  const charted = rows.filter((row) => row.color < MAX_SERIES);
  const keys = rows[0].metrics.map((m) => ({ key: m.key, label: m.label }));
  const of = (row: (typeof rows)[number], key: string): BreakdownMetric | undefined => row.metrics.find((m) => m.key === key);

  return (
    <section aria-labelledby="report-by-account" className="space-y-3" data-testid="account-breakdown">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="report-by-account" className={CARD_TITLE}>
          Account by account
        </h2>
        <ChartLegend
          label="Accounts"
          items={rows.map((row) => ({ key: row.account.id, label: row.account.name, color: row.color, shape: "box" as const }))}
        />
      </div>

      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[40rem] border-collapse text-sm" data-testid="breakdown-table">
          <caption className="sr-only">Each account&apos;s figures this week, with the change from the week before</caption>
          <thead>
            <tr className="border-b border-line text-left text-xs text-fg-secondary">
              <th scope="col" className="px-3 py-2 font-medium">
                Account
              </th>
              {keys.map((k) => (
                <th key={k.key} scope="col" className="px-3 py-2 text-right font-medium">
                  {k.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.account.id} data-account={row.account.id} className="border-b border-line-subtle last:border-b-0">
                <th scope="row" className="px-3 py-2 text-left font-medium">
                  <AccountMark account={row.account} color={row.color} />
                </th>
                {keys.map((k) => {
                  const m = of(row, k.key);
                  return (
                    <td key={k.key} data-cell={k.key} className="px-3 py-2 text-right align-top tabular-nums">
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

      <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
        {keys.map((k) => (
          <li key={k.key} data-breakdown={k.key} className="min-w-0">
            <MetricCard label={k.label} metricKey={k.key} rows={charted} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function AccountMark({ account, color }: { account: ReportAccount; color: number }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span aria-hidden className={cn("size-2.5 shrink-0 rounded-sm", seriesStyle(color).bg)} />
      <PlatformGlyph platform={account.platform as Platform} className="size-4 shrink-0" />
      <span className="truncate">{account.name}</span>
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
  const trend = reportTrend(metric);
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className="font-semibold">{formatMetric("count", metric.value)}</span>
      {trend ? <TrendChip trend={trend} /> : null}
    </span>
  );
}

function MetricCard({ label, metricKey, rows }: { label: string; metricKey: string; rows: (Breakdown & { color: number })[] }) {
  const entries = rows.map((row) => ({ row, metric: row.metrics.find((m) => m.key === metricKey) })).filter((e): e is { row: Breakdown & { color: number }; metric: BreakdownMetric } => !!e.metric);
  const withData = entries.filter((e) => e.metric.series.some((p) => p.value !== null && p.value !== undefined));
  const first = entries[0]?.metric.series ?? [];
  const bars: BarRow[] = entries.map(({ row, metric }) => ({
    key: row.account.id,
    name: row.account.name,
    label: <AccountMark account={row.account} color={row.color} />,
    color: row.color,
    value: metric.value,
    previous: metric.previous,
    unavailable: metric.value === null || metric.value === undefined ? unavailableWords(metric.unavailable) : null,
  }));
  const change = (bar: BarRow) => {
    const found = entries.find((e) => e.row.account.id === bar.key)?.metric;
    return found ? changeText(found) : null;
  };
  return (
    <Card className="h-full space-y-3">
      <CardTitle className="text-sm">{label}</CardTitle>
      <BarChart label={`${label} by account, this week against last week`} rows={bars} format={(v) => formatMetric("count", v)} change={change} />
      {withData.length > 0 ? (
        <LineChart
          height={120}
          label={`${label} by account, week by week`}
          legend={false}
          beforeLabel="Week before"
          format={(v) => formatMetric("count", v)}
          points={first.map((p) => ({ key: p.week_start, label: dayLabel(p.week_start), title: weekLabel(p.week_start) }))}
          series={withData.map(({ row, metric }) => ({ key: row.account.id, label: row.account.name, color: row.color, values: metric.series.map((p) => p.value) }))}
        />
      ) : (
        <p className="text-sm text-fg-secondary">No readings in these weeks.</p>
      )}
    </Card>
  );
}
