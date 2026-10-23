"use client";

import * as Sentry from "@sentry/nextjs";
import { Component, type ErrorInfo, type ReactNode } from "react";

import type { Visual } from "@/lib/api/types";

import { MetricComparison } from "./visuals/MetricComparison";
import { RankedPosts } from "./visuals/RankedPosts";
import { SentimentSummary } from "./visuals/SentimentSummary";

/**
 * A visual that fails to draw is hidden and reported (Sentry, tagged with its kind), so the text
 * answer, the sources and the actions under it stay. Nothing in a visual is worth losing the page.
 */
class VisualBoundary extends Component<{ kind: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    Sentry.captureException(error, {
      tags: { area: "agent_visual", visual_kind: this.props.kind },
      extra: { componentStack: info.componentStack },
    });
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * GR-38: one visual answer, by its kind (docs/architecture/generative-ui/05). The set is closed:
 * the API builds every visual from service numbers and the web draws it with its own components.
 * A kind this build doesn't know (the API ahead of the web during a deploy) draws nothing; the
 * answer and its sources still stand.
 */
export function VisualView({
  visual,
  slug,
  onNavigate,
}: {
  visual: Visual;
  slug: string;
  /** Following a link leaves the Ask panel: the caller closes it. */
  onNavigate?: () => void;
}) {
  return (
    <VisualBoundary kind={visual.kind}>
      <div data-testid="visual" data-kind={visual.kind}>
        <Drawn visual={visual} slug={slug} onNavigate={onNavigate} />
      </div>
    </VisualBoundary>
  );
}

function Drawn({ visual, slug, onNavigate }: { visual: Visual; slug: string; onNavigate?: () => void }) {
  switch (visual.kind) {
    case "metric_comparison":
      return <MetricComparison visual={visual} />;
    case "ranked_posts":
      return <RankedPosts visual={visual} slug={slug} onNavigate={onNavigate} />;
    case "sentiment_summary":
      return <SentimentSummary visual={visual} />;
    default:
      return null;
  }
}
