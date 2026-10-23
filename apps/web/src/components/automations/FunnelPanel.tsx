"use client";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAutomationFunnel } from "@/lib/api/queries";
import type { AutomationFunnel, FunnelStep, SplitResult } from "@/lib/api/types";
import { formatCount } from "@/lib/automations/format";
import { cn } from "@/lib/utils";
import { EYEBROW } from "@/styles/tokens";

/** The figures worth showing for one step: only those that can happen at its kind of step. */
export function stepFigures(step: FunnelStep): { label: string; value: string }[] {
  const out = [{ label: "Reached", value: formatCount(step.reached) }];
  if (step.kind === "send" || step.kind === "ask") {
    out.push({ label: "Sent", value: formatCount(step.sent) });
    out.push({ label: "Delivered", value: formatCount(step.delivered) });
    // A read receipt only where the platform sends one.
    if (step.read > 0) out.push({ label: "Read", value: formatCount(step.read) });
  }
  if (step.quick_replies > 0 || step.taps > 0) out.push({ label: "Taps", value: formatCount(step.taps) });
  if (step.link_buttons > 0 || step.link_clicks > 0) {
    out.push({
      label: "Link clicks",
      value:
        step.link_clicks > 0
          ? `${formatCount(step.link_clicks)} (${formatCount(step.link_clickers)} ${step.link_clickers === 1 ? "person" : "people"})`
          : "0",
    });
  }
  if (step.kind === "ask") {
    out.push({ label: "Answers", value: formatCount(step.captures) });
    if (step.skipped > 0) out.push({ label: "Skipped", value: formatCount(step.skipped) });
    if (step.consents > 0) out.push({ label: "Said yes to marketing", value: formatCount(step.consents) });
  }
  if (step.failed > 0) out.push({ label: "Failed", value: formatCount(step.failed) });
  return out;
}

/**
 * GR-15: what happened at each step of the flow, then each Split's paths. Only steps that anyone
 * reached show figures; the rest stay as a quiet line so the flow's shape is still visible.
 */
export function FunnelPanel({ wid, automationId, days }: { wid: string; automationId: string; days: 7 | 30 }) {
  const funnel = useAutomationFunnel(wid, automationId, days);
  if (funnel.isPending) {
    return (
      <div role="status" aria-busy="true" aria-label="Loading step results" className="space-y-2">
        <Skeleton className="h-16 rounded-lg" />
        <Skeleton className="h-16 rounded-lg" />
      </div>
    );
  }
  if (funnel.isError) {
    return (
      <div className="flex items-center justify-between gap-2 text-sm text-fg-secondary">
        <p>Step results didn&apos;t load.</p>
        <Button variant="ghost" size="sm" onClick={() => void funnel.refetch()}>
          Retry step results
        </Button>
      </div>
    );
  }
  return <FunnelView funnel={funnel.data} />;
}

export function FunnelView({ funnel }: { funnel: AutomationFunnel }) {
  const hasLinks = funnel.steps.some((step) => step.link_buttons > 0);
  return (
    <section aria-label="Results by step" className="space-y-3" data-testid="funnel">
      <p className={EYEBROW}>By step</p>
      {hasLinks && !funnel.links_tracked ? (
        <p className="text-xs text-fg-secondary" data-testid="links-untracked">
          Link tracking is off for this automation, so clicks aren&apos;t counted. Turn it on in Settings.
        </p>
      ) : null}
      <ol className="space-y-2">
        {funnel.steps.map((step, index) => (
          <li
            key={step.step_id}
            data-testid="funnel-step"
            data-step={step.step_id}
            className={cn("rounded-lg border border-line p-3", step.reached === 0 && "opacity-70")}
          >
            <p className="text-sm font-medium">
              <span className="text-fg-secondary tabular-nums">{index + 1}. </span>
              {step.title}
            </p>
            {step.text ? <p className="mt-0.5 line-clamp-2 text-xs text-fg-secondary">{step.text}</p> : null}
            <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {stepFigures(step).map((figure) => (
                <span key={figure.label}>
                  <span className="text-fg-secondary">{figure.label}</span>{" "}
                  <span className="tabular-nums">{figure.value}</span>
                </span>
              ))}
            </p>
          </li>
        ))}
      </ol>
      {funnel.splits.map((split) => (
        <SplitTable key={split.step_id} split={split} number={funnel.steps.findIndex((s) => s.step_id === split.step_id) + 1} />
      ))}
    </section>
  );
}

/** One Split step's paths side by side; a column shows only when some path has something in it. */
function SplitTable({ split, number }: { split: SplitResult; number: number }) {
  const total = (pick: (branch: SplitResult["branches"][number]) => number) =>
    split.branches.reduce((sum, branch) => sum + pick(branch), 0);
  const columns = [
    { label: "Runs", value: (b: SplitResult["branches"][number]) => b.runs, always: true },
    { label: "Delivered", value: (b: SplitResult["branches"][number]) => b.delivered, always: true },
    { label: "Read", value: (b: SplitResult["branches"][number]) => b.read, always: false },
    { label: "Taps", value: (b: SplitResult["branches"][number]) => b.taps, always: false },
    { label: "Link clicks", value: (b: SplitResult["branches"][number]) => b.link_clicks, always: false },
    { label: "Answers", value: (b: SplitResult["branches"][number]) => b.captures, always: false },
  ].filter((column) => column.always || total(column.value) > 0);
  return (
    <div className="space-y-1" data-testid="split-results">
      <p className={EYEBROW}>Split{number > 0 ? ` (step ${number})` : ""}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Results for each path of the split</caption>
          <thead>
            <tr className="text-left text-xs text-fg-secondary">
              <th scope="col" className="py-1 pr-3 font-normal">
                Path
              </th>
              {columns.map((column) => (
                <th key={column.label} scope="col" className="px-2 py-1 text-right font-normal">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {split.branches.map((branch) => (
              <tr key={branch.path} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {branch.label} <span className="text-xs text-fg-secondary">weight {branch.weight}</span>
                </th>
                {columns.map((column) => (
                  <td key={column.label} className="px-2 py-1.5 text-right tabular-nums">
                    {formatCount(column.value(branch))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
