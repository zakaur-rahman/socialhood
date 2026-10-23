"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { MetricComparison } from "@/components/agent/visuals/MetricComparison";
import { formatCount, formatSpan } from "@/components/home/format";
import { MetricTile } from "@/components/home/MetricTile";
import { PageFrame } from "@/components/shell/PageFrame";
import { ErrorState } from "@/components/states/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { INTENT_LABEL } from "@/lib/ai/format";
import { useWeeklyReport } from "@/lib/api/queries";
import type { ReportAccountMetric, ReportMetric, WeeklyReport } from "@/lib/api/types";
import { formatMetric, parseWeekParam, previousLine, reportTrend, weekLabel } from "@/lib/reports/format";
import { useCurrentWorkspace } from "@/lib/workspace";
import { CARD_TITLE } from "@/styles/tokens";

import { SeriesChart } from "./SeriesChart";

/**
 * The weekly report (GR-34, roadmap P3; VIS-13): one finished Monday to Sunday against the week
 * before, and each main count over the weeks leading up to it. The week is in the address
 * (`?week=2026-09-21`), so a link from the digest email or a colleague opens that week; any member
 * of the workspace can open it, and there is no public link. Every number and change is the
 * API's (the digest email carries the same ones), a week with no figure says so instead of
 * showing 0, and the account figures use the same cards as Ask's comparisons. It works from
 * 320 px: one column of tiles, two from 640 px, three from 1280 px.
 */
export function WeeklyReportPage() {
  const workspace = useCurrentWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const week = parseWeekParam(params?.get("week"));
  const report = useWeeklyReport(workspace.id, week);
  const data = report.data;

  const open = (monday: string) => router.replace(`${pathname}?week=${monday}` as Route);

  return (
    <PageFrame title="Weekly report" actions={data ? <WeekPicker report={data} onPick={open} switching={report.isPlaceholderData} /> : null}>
      {report.isPending ? (
        <div role="status" aria-busy="true" aria-label="Loading the weekly report" className="space-y-6">
          <Skeleton className="h-5 w-64 max-w-full" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-40 rounded-xl" />
            ))}
          </div>
        </div>
      ) : !data ? (
        <div className="space-y-3">
          <ErrorState error={report.error} onRetry={() => void report.refetch()} />
          {week ? (
            <p className="text-center">
              <Button variant="outline" onClick={() => router.replace(pathname as Route)}>
                Show the latest week
              </Button>
            </p>
          ) : null}
        </div>
      ) : (
        <Report data={data} slug={workspace.slug} switching={report.isPlaceholderData} />
      )}
    </PageFrame>
  );
}

function WeekPicker({ report, onPick, switching }: { report: WeeklyReport; onPick: (monday: string) => void; switching: boolean }) {
  const index = report.weeks.indexOf(report.week_start);
  const newer = index > 0 ? report.weeks[index - 1] : null;
  const older = index >= 0 && index < report.weeks.length - 1 ? report.weeks[index + 1] : null;
  // A week asked for by address may be older than the picker's list: it stays selectable.
  const options = index >= 0 ? report.weeks : [report.week_start, ...report.weeks];
  return (
    <div role="group" aria-label="Choose a week" aria-busy={switching} className="flex items-center gap-1">
      <Button
        variant="outline"
        size="icon"
        aria-label="Earlier week"
        disabled={!older}
        onClick={() => older && onPick(older)}
      >
        <ChevronLeft aria-hidden />
      </Button>
      <Select value={report.week_start} onValueChange={onPick}>
        <SelectTrigger aria-label="Week" className="w-44">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((monday) => (
            <SelectItem key={monday} value={monday}>
              {weekLabel(monday)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        variant="outline"
        size="icon"
        aria-label="Later week"
        disabled={!newer}
        onClick={() => newer && onPick(newer)}
      >
        <ChevronRight aria-hidden />
      </Button>
    </div>
  );
}

function Report({ data, slug, switching }: { data: WeeklyReport; slug: string; switching: boolean }) {
  const span = formatSpan(data.week.since, data.week.until);
  const before = formatSpan(data.previous_week.since, data.previous_week.until);
  return (
    <div className="space-y-8" aria-busy={switching} data-testid="weekly-report">
      <p className="text-sm text-fg-secondary" data-testid="report-span">
        <span className="font-medium text-fg tabular-nums">{span}</span>, Monday to Sunday in {data.timezone}, against {before}. Charts show the{" "}
        {data.series_weeks} weeks up to this one.
      </p>

      <section aria-labelledby="report-counts" className="space-y-3">
        <h2 id="report-counts" className={CARD_TITLE}>
          Conversations and leads
        </h2>
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.metrics.map((metric) => (
            <MetricItem key={metric.key} metric={metric} />
          ))}
        </ul>
      </section>

      <section aria-labelledby="report-account" className="space-y-3">
        <h2 id="report-account" className={CARD_TITLE}>
          Your Instagram account
        </h2>
        <MetricComparison visual={data.account_comparison} />
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.account_metrics.map((item) => (
            <AccountSeries key={item.figure.metric} item={item} />
          ))}
        </ul>
      </section>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <IntentsCard report={data} />
        <PostsCard report={data} slug={slug} />
        <OpenCard report={data} slug={slug} />
      </div>
    </div>
  );
}

function MetricItem({ metric }: { metric: ReportMetric }) {
  return (
    <li data-metric={metric.key} className="flex min-w-0 flex-col gap-1">
      <MetricTile label={metric.label} value={formatMetric(metric.unit, metric.value)} trend={reportTrend(metric)} hint={previousLine(metric)} />
      <SeriesChart label={metric.label} unit={metric.unit} series={metric.series} className="px-1" />
    </li>
  );
}

function AccountSeries({ item }: { item: ReportAccountMetric }) {
  const known = item.series.some((p) => p.value !== null && p.value !== undefined);
  return (
    <li data-account-metric={item.figure.metric} className="min-w-0 space-y-1 rounded-xl border border-line p-3">
      <p className="text-xs text-fg-secondary">{item.label}, by week</p>
      {known ? (
        <SeriesChart label={item.label} unit="count" series={item.series} />
      ) : (
        <p className="text-sm text-fg-secondary">No readings in these weeks.</p>
      )}
    </li>
  );
}

function IntentsCard({ report }: { report: WeeklyReport }) {
  const most = Math.max(1, ...report.top_intents.map((i) => i.count));
  return (
    <Card asChild className="flex flex-col">
      <section aria-labelledby="report-intents">
        <CardTitle id="report-intents" className="mb-3">
          What customers asked about
        </CardTitle>
        {report.top_intents.length === 0 ? (
          <p className="text-sm text-fg-secondary">Topics appear once the AI has read messages from this week.</p>
        ) : (
          <ol className="space-y-3">
            {report.top_intents.map((item) => (
              <li key={item.intent} className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{INTENT_LABEL[item.intent as keyof typeof INTENT_LABEL] ?? item.intent}</span>
                  <span className="text-xs text-fg-secondary tabular-nums">
                    {formatCount(item.count)} {item.count === 1 ? "message" : "messages"}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-raised" aria-hidden>
                  <div className="h-full rounded-full bg-chart-series-1" style={{ width: `${(item.count / most) * 100}%` }} />
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </Card>
  );
}

function PostsCard({ report, slug }: { report: WeeklyReport; slug: string }) {
  return (
    <Card asChild className="flex flex-col">
      <section aria-labelledby="report-posts">
        <CardTitle id="report-posts" className="mb-3">
          Posts with the most comments
        </CardTitle>
        {report.top_posts.length === 0 ? (
          <p className="text-sm text-fg-secondary">No comments on any post this week.</p>
        ) : (
          <ol className="space-y-2">
            {report.top_posts.map((post) => (
              <li key={post.id} className="flex items-baseline justify-between gap-3 text-sm">
                <Link
                  href={`/w/${slug}/comments/${post.id}` as Route}
                  className="min-w-0 truncate font-medium hover:underline"
                >
                  {post.caption?.trim().split("\n")[0] || "Post without a caption"}
                </Link>
                <span className="shrink-0 text-xs text-fg-secondary tabular-nums">
                  {formatCount(post.comments)} {post.comments === 1 ? "comment" : "comments"}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </Card>
  );
}

/** Where things stand now, not in the week: the inbox and the knowledge gaps are live counts. */
function OpenCard({ report, slug }: { report: WeeklyReport; slug: string }) {
  return (
    <Card asChild className="flex flex-col">
      <section aria-labelledby="report-open">
        <CardTitle id="report-open" className="mb-3">
          Open right now
        </CardTitle>
        <ul className="space-y-2 text-sm">
          <li>
            <Link href={`/w/${slug}/inbox` as Route} className="hover:underline">
              <span className="font-semibold tabular-nums">{formatCount(report.needs_you)}</span>{" "}
              {report.needs_you === 1 ? "conversation needs" : "conversations need"} you
            </Link>
          </li>
          <li>
            <Link href={`/w/${slug}/knowledge` as Route} className="hover:underline">
              <span className="font-semibold tabular-nums">{formatCount(report.open_questions)}</span>{" "}
              {report.open_questions === 1 ? "question the AI couldn't answer" : "questions the AI couldn't answer"}
            </Link>
          </li>
        </ul>
        {report.top_questions.length > 0 ? (
          <ul className="mt-3 space-y-1 border-t border-line-subtle pt-3 text-xs text-fg-secondary">
            {report.top_questions.map((q) => (
              <li key={q.topic} className="flex justify-between gap-3">
                <span className="min-w-0 truncate">{q.topic}</span>
                <span className="shrink-0 tabular-nums">asked {formatCount(q.asked)}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </Card>
  );
}
