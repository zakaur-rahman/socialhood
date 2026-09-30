"use client";

import {
  BookOpen,
  CalendarClock,
  Clock,
  CreditCard,
  ExternalLink,
  Gauge,
  Layers,
  Sparkles,
  Zap,
} from "lucide-react";
import type { Route } from "next";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { PLATFORM_BG, PlatformGlyph } from "@/components/connections/PlatformGlyph";
import { SettingsCard } from "@/components/settings/SettingsCard";
import { SettingsFrame, SettingsPageHeader } from "@/components/settings/SettingsPageHeader";
import { ErrorState } from "@/components/states/ErrorState";
import { PageSkeleton } from "@/components/states/PageSkeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useBilling, useBillingPlans, useCancelPlan, useResumePlan } from "@/lib/api/queries";
import type { BillingState } from "@/lib/api/types";
import {
  TRIAL_DAYS,
  billingDate,
  canCheckout,
  meterViews,
  planStatus,
  priceOf,
  type MeterView,
  type StatusTone,
} from "@/lib/billing/plan";
import { PLAN_NAME, billingCopy, errorMessage, limitText, planIncludes, pricePerMonth } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { useCurrentWorkspace } from "@/lib/workspace";

import {
  CONFIRM_POLL_MS,
  CONFIRM_TIMEOUT_MS,
  CheckoutReturn,
  isConfirmed,
  useCheckoutConfirmation,
} from "./CheckoutReturn";
import { PaymentHistory } from "./PaymentHistory";
import { PlanCards } from "./PlanCards";
import { meterLevel, type MeterLevel } from "./UsageMeter";
import { useOpenPortal, useStartCheckout } from "./use-billing-actions";

const BADGE: Record<StatusTone, string> = {
  neutral: "bg-white/10 text-fg-secondary",
  brand: "bg-brand-soft text-brand-fg",
  warning: "bg-warning/15 text-warning",
  danger: "bg-danger/15 text-danger-fg",
};

/** The entitlement key each usage metric is limited by, for "Free includes …" at 100 %. */
const ENTITLEMENT_FOR_METRIC: Record<string, string> = {
  ai_credits: "ai_credits_monthly",
  scheduled_posts: "scheduled_posts_monthly",
  instagram_accounts: "accounts_per_platform",
  whatsapp_accounts: "accounts_per_platform",
};

const METER_ICON: Record<string, ReactNode> = {
  ai_credits: <Sparkles />,
  scheduled_posts: <CalendarClock />,
  knowledge_characters: <BookOpen />,
  active_automations: <Zap />,
  pending_scheduled_messages: <Clock />,
  instagram_accounts: <PlatformGlyph platform="instagram" />,
  whatsapp_accounts: <PlatformGlyph platform="whatsapp" />,
};

const METER_ICON_BG: Record<string, string> = {
  instagram_accounts: `${PLATFORM_BG.instagram} text-white`,
  whatsapp_accounts: `${PLATFORM_BG.whatsapp} text-white`,
};

const FILL: Record<MeterLevel, string> = {
  normal: "bg-brand-gradient-decor",
  warning: "bg-warning",
  full: "bg-danger",
};

const count = new Intl.NumberFormat("en-US");

/** FR-BIL-07, said before the owner cancels: what moving to Free changes. Nothing is deleted. */
const DOWNGRADE_EFFECTS =
  "Accounts in Auto switch to Suggest, AI-reply automations pause, automations over Free's limit pause and extra accounts become read-only. Nothing is deleted.";

/**
 * UX-SCR-07 Billing, F-15, FR-BIL-02…06: the current plan and its status, usage meters for every
 * limited entitlement, the plans, and the owner's actions (checkout, Manage billing in Dodo's
 * portal, cancel and resume, each confirmed). After checkout Dodo returns here with
 * ?checkout=return; the page waits for the webhook and never assumes the payment worked.
 * Owners manage; admins see it read-only; agents are sent to their own notification settings.
 * C-066: a plan hero, a grid of quota meters, the plans side by side and the payment history.
 */
export function BillingPage() {
  const workspace = useCurrentWorkspace();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const agent = workspace.role === "agent";
  const [returned] = useState(() => params.get("checkout") === "return");
  const returnedAt = useRef<number | null>(null);
  useEffect(() => {
    if (returned) returnedAt.current ??= Date.now();
  }, [returned]);
  const billing = useBilling(workspace.id, !agent, {
    // F-15: poll every 3 s for up to 60 s while waiting for the webhook (usage.updated refetches
    // sooner when it arrives).
    refetchInterval: (query) =>
      returned &&
      !isConfirmed(query.state.data) &&
      (returnedAt.current === null || Date.now() - returnedAt.current < CONFIRM_TIMEOUT_MS)
        ? CONFIRM_POLL_MS
        : false,
  });
  const phase = useCheckoutConfirmation(returned, billing.data);
  const [noticeDone, setNoticeDone] = useState(false);
  const plans = useBillingPlans(!agent);
  const checkout = useStartCheckout(workspace.id);

  useEffect(() => {
    if (agent) router.replace(`/w/${workspace.slug}/settings/notifications` as Route);
  }, [agent, router, workspace.slug]);

  // Drop ?checkout=return from the address once read, so a reload doesn't wait again.
  useEffect(() => {
    if (returned && params.get("checkout")) router.replace(pathname as Route, { scroll: false });
  }, [returned, params, pathname, router]);

  if (agent || billing.isPending) return <PageSkeleton rows={3} />;
  if (billing.isError) return <ErrorState error={billing.error} onRetry={() => void billing.refetch()} />;

  const state = billing.data;
  const isOwner = workspace.role === "owner";
  return (
    <SettingsFrame
      header={
        <SettingsPageHeader
          label="Plan & usage"
          title="Billing & Usage"
          description="Your plan, what this workspace has used of it, and every payment."
        />
      }
    >
      <div className="space-y-6">
        {phase && !noticeDone ? (
          <CheckoutReturn phase={phase} billing={state} onDone={() => setNoticeDone(true)} />
        ) : null}
        <CurrentPlan
          billing={state}
          isOwner={isOwner}
          checkout={checkout}
          trialDays={plans.data?.items.find((offer) => offer.plan === "pro")?.trial_days || TRIAL_DAYS}
        />
        <Usage billing={state} />
        <section aria-labelledby="plans-title" className="space-y-4">
          <div className="space-y-1">
            <h2 id="plans-title" className="text-lg font-semibold tracking-tight">
              Compare plans
            </h2>
            <p className="text-sm text-fg-secondary">What each plan includes. Max is coming soon.</p>
          </div>
          <PlanCards plans={plans} billing={state} isOwner={isOwner} checkout={checkout} />
        </section>
        <PaymentHistory />
      </div>
    </SettingsFrame>
  );
}

function CurrentPlan({
  billing,
  isOwner,
  checkout,
  trialDays,
}: {
  billing: BillingState;
  isOwner: boolean;
  checkout: ReturnType<typeof useStartCheckout>;
  trialDays: number;
}) {
  const workspace = useCurrentWorkspace();
  const portal = useOpenPortal(workspace.id);
  const cancel = useCancelPlan(workspace.id);
  const resume = useResumePlan(workspace.id);
  const [confirm, setConfirm] = useState<"cancel" | "resume" | null>(null);
  const status = planStatus(billing, workspace.timezone);
  const name = PLAN_NAME[billing.plan];
  const periodEnd = billing.status === "trialing" ? (billing.trial_ends_at ?? billing.current_period_end) : billing.current_period_end;
  const endsOn = periodEnd ? billingDate(periodEnd, workspace.timezone) : null;
  const price = priceOf(billing.plan, billing);
  const mayCheckout = canCheckout(billing);
  const trial = billing.status === "trialing";

  const runCancel = () =>
    cancel.mutate(undefined, {
      onSuccess: (next) => {
        const date = next.current_period_end ?? next.trial_ends_at;
        toast.success(date ? billingCopy.cancelled(name, billingDate(date, workspace.timezone)) : "Cancelled");
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  const runResume = () =>
    resume.mutate(undefined, {
      onSuccess: () => toast.success(billingCopy.resumed(name)),
      onError: (error) => toast.error(errorMessage(error)),
    });

  const actions = isOwner ? (
    <div className="flex flex-wrap gap-2 md:justify-end">
      {mayCheckout ? (
        <Button
          className="bg-brand-gradient min-h-10 text-white md:min-h-9"
          disabled={checkout.pending}
          onClick={() => checkout.start("pro")}
        >
          {checkout.pending
            ? "Opening checkout…"
            : billing.trial_eligible
              ? billingCopy.trialCta(trialDays)
              : billingCopy.upgradeCta}
        </Button>
      ) : null}
      {billing.status !== "free" ? (
        <Button
          variant={billing.status === "on_hold" ? "default" : "secondary"}
          className={cn("min-h-10 md:min-h-9", billing.status === "on_hold" && "bg-brand-gradient text-white")}
          disabled={portal.pending}
          onClick={portal.open}
        >
          <ExternalLink aria-hidden /> {billing.status === "on_hold" ? "Update payment method" : "Manage billing"}
        </Button>
      ) : null}
      {status.resumable ? (
        <Button variant="secondary" className="min-h-10 md:min-h-9" disabled={resume.isPending} onClick={() => setConfirm("resume")}>
          {resume.isPending ? "Resuming…" : `Resume ${name}`}
        </Button>
      ) : null}
      {status.cancellable ? (
        <Button variant="ghost" className="min-h-10 text-fg-secondary md:min-h-9" disabled={cancel.isPending} onClick={() => setConfirm("cancel")}>
          {cancel.isPending ? "Cancelling…" : trial ? "Cancel trial" : "Cancel plan"}
        </Button>
      ) : null}
    </div>
  ) : (
    <p className="text-sm text-fg-secondary">{billingCopy.ownerOnly}</p>
  );

  return (
    <section
      aria-labelledby="plan-title"
      className="space-y-4 rounded-2xl border border-brand-line bg-panel bg-[radial-gradient(120%_140%_at_0%_0%,var(--color-brand-soft),transparent_60%)] p-5 md:p-6"
    >
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span aria-hidden className="bg-shell-gradient grid size-12 shrink-0 place-items-center rounded-xl text-white">
            <CreditCard className="size-6" />
          </span>
          <div className="min-w-0 space-y-1">
            <p className="text-[11px] font-semibold tracking-[0.12em] text-fg-secondary uppercase">Current plan</p>
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="plan-title" className="text-2xl font-semibold tracking-tight">
                {status.plan}
              </h2>
              <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", BADGE[status.badge.tone])}>
                {status.badge.label}
              </span>
            </div>
            <p className={cn("text-sm", status.badge.tone === "danger" ? "text-danger-fg" : "text-fg-secondary")}>
              {status.line}
            </p>
          </div>
        </div>
        {actions}
      </div>
      {checkout.error ? (
        <p role="alert" className="text-sm text-danger-fg">
          {checkout.error}
        </p>
      ) : null}

      <AlertDialog open={confirm !== null} onOpenChange={(open) => (open ? undefined : setConfirm(null))}>
        <AlertDialogContent className="border-line bg-panel sm:max-w-md">
          {confirm === "cancel" ? (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>{trial ? "Cancel the trial?" : `Cancel ${name}?`}</AlertDialogTitle>
                <AlertDialogDescription className="text-fg-secondary">
                  {trial
                    ? `${name} stays until the trial ends${endsOn ? ` on ${endsOn}` : ""}, and your card isn't charged. `
                    : `${name} stays until ${endsOn ?? "the end of this billing period"}. `}
                  Then the workspace moves to Free. {DOWNGRADE_EFFECTS}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter className="border-line bg-transparent">
                <AlertDialogCancel className="min-h-10 md:min-h-8">Keep {name}</AlertDialogCancel>
                <AlertDialogAction variant="destructive" className="min-h-10 md:min-h-8" onClick={runCancel}>
                  {trial ? "Cancel trial" : "Cancel plan"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </>
          ) : (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>Resume {name}?</AlertDialogTitle>
                <AlertDialogDescription className="text-fg-secondary">
                  {`${name} renews${endsOn ? ` on ${endsOn}` : ""}${price ? ` at ${pricePerMonth(price)}` : ""}, and the workspace keeps its limits.`}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter className="border-line bg-transparent">
                <AlertDialogCancel className="min-h-10 md:min-h-8">Not now</AlertDialogCancel>
                <AlertDialogAction className="bg-brand-gradient min-h-10 text-white md:min-h-8" onClick={runResume}>
                  Resume {name}
                </AlertDialogAction>
              </AlertDialogFooter>
            </>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

/**
 * FR-BIL-05 "Resource quotas & usage" (C-066): a meter for every limit GET …/billing counts, with
 * its percentage and, for a monthly allowance, when it resets; warning at 80 % and danger at
 * 100 %. The plan's other limits are listed (the UI never counts usage itself, TR-BIL-04).
 */
function Usage({ billing }: { billing: BillingState }) {
  const workspace = useCurrentWorkspace();
  const meters = meterViews(billing.usage, workspace.timezone);
  const metered = new Set(meters.map((meter) => ENTITLEMENT_FOR_METRIC[meter.metric] ?? meter.metric));
  const others = billing.entitlements.flatMap((item) =>
    typeof item.value === "number" && !metered.has(item.key) ? [limitText(item.key, item.value)] : [],
  ).filter((line): line is string => Boolean(line));
  if (meters.length === 0 && others.length === 0) return null;
  return (
    <SettingsCard
      id="usage"
      icon={<Gauge />}
      title="Resource quotas & usage"
      description={`What this workspace has used of ${PLAN_NAME[billing.plan]}'s limits.`}
    >
      {meters.length > 0 ? (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Usage">
          {meters.map((meter) => {
            const key = ENTITLEMENT_FOR_METRIC[meter.metric] ?? meter.metric;
            return (
              <QuotaTile
                key={meter.metric}
                meter={meter}
                fullMessage={meter.limit ? (planIncludes(key, meter.limit, billing.plan) ?? undefined) : undefined}
              />
            );
          })}
        </ul>
      ) : null}
      {others.length > 0 ? (
        <div className="mt-5 space-y-1.5 border-t border-line-subtle pt-4">
          <p className="flex items-center gap-2 text-xs font-medium text-fg-secondary">
            <Layers className="size-3.5" aria-hidden />
            {PLAN_NAME[billing.plan]} also includes
          </p>
          <ul className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2" aria-label="Other limits">
            {others.map((line) => (
              <li key={line}>{line.charAt(0).toUpperCase() + line.slice(1)}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </SettingsCard>
  );
}

function percentText(used: number, limit: number): string {
  const share = (used / limit) * 100;
  if (used > 0 && share < 1) return "<1%";
  return `${Math.min(999, Math.round(share))}%`;
}

/** One quota: label, percentage, "{used} / {limit} {unit}", a bar, and when it resets. */
function QuotaTile({ meter, fullMessage }: { meter: MeterView; fullMessage?: string }) {
  const limit = meter.limit ?? 0;
  const level = meterLevel(meter.used, limit);
  const width = limit ? Math.min(100, Math.round((meter.used / limit) * 100)) : 0;
  const valueText = `${count.format(meter.used)} of ${count.format(limit)} ${meter.unit}`.trim();
  return (
    <li data-level={level} className="flex min-w-0 flex-col gap-3 rounded-xl border border-line-subtle bg-field/60 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            aria-hidden
            className={cn(
              "grid size-8 shrink-0 place-items-center rounded-lg bg-raised text-brand-fg [&_svg]:size-4",
              METER_ICON_BG[meter.metric],
            )}
          >
            {METER_ICON[meter.metric] ?? <Gauge />}
          </span>
          <p className="text-sm font-medium">{meter.label}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums",
            level === "full" ? "bg-danger/15 text-danger-fg" : level === "warning" ? "bg-warning/15 text-warning" : "bg-raised text-fg-secondary",
          )}
        >
          {percentText(meter.used, limit)}
        </span>
      </div>
      <p className="text-sm text-fg-secondary tabular-nums">
        <span className="text-lg font-semibold text-fg">{count.format(meter.used)}</span> / {count.format(limit)}{" "}
        {meter.unit}
      </p>
      <div
        role="meter"
        aria-label={meter.label}
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={Math.min(meter.used, limit)}
        aria-valuetext={valueText}
        className="h-1.5 overflow-hidden rounded-full bg-raised"
      >
        <span className={cn("block h-full rounded-full", FILL[level])} style={{ width: `${width}%` }} />
      </div>
      {meter.note ? <p className="text-xs text-fg-secondary">{meter.note}</p> : null}
      {level === "full" && fullMessage ? (
        <p className="text-xs text-danger-fg" role="status">
          {fullMessage}
        </p>
      ) : null}
    </li>
  );
}
