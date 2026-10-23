# 05 · Response contract

The typed contract between the agent's tools, the API and the web for visual answers. It follows the existing `ActionCard` pattern: a discriminated union in `api/schemas/agent.py`, derived when the run is read, generated into `packages/api-client`, and rendered by a switch on `kind`.

## 1. Where it lives

| Layer | File | Change |
|---|---|---|
| Visual models (Pydantic) | `api/schemas/agent.py` (beside `ActionCard`) | `Visual` union plus its parts (below) |
| Tool results | `api/agent/tools/analytics.py` (and later `contacts`, `comments`) | Result models gain `visual: Visual \| None = None`, built by server code from the same data |
| Model view | `api/agent/report.py::model_view` | Drop `visual` from what the model sees (it holds the same numbers; saves tokens) |
| Run output | `api/services/agent_runs.py::run_out` | `AgentRun.visuals: list[Visual]`, from the successful steps in order, at most `MAX_VISUALS = 3` |
| Run list | same | `AgentRunList` items **omit** visuals (thread view loads 20 runs; fetch detail lazily), or include them capped. Decide in VIS-02; recommended: include, since each visual is ≤ 8 KB |
| Contract | `pnpm gen:api` | CI `contract` job enforces it |
| Web types | `web/lib/api/types.ts` | `export type Visual = AgentRun["visuals"][number]` |
| Web render | `web/components/agent/VisualView.tsx` (new), used in `RunView.Finished` between `AnswerText` and the action cards | Exhaustive `switch (visual.kind)` with `assertNever` |

**No database migration:** `agent_steps.result` (JSONB) already stores the whole result.

## 2. Schemas (Pydantic, server)

```python
# api/schemas/agent.py
VISUAL_VERSION = 1

class MetricValue(ResponseModel):
    key: Literal["reach", "views", "interactions", "followers", "follows", "unfollows",
                 "profile_link_taps", "likes", "comments", "shares", "saves", "engagement_rate",
                 "messages_received", "reply_rate"]
    label: str                      # server copy, e.g. "Reach"
    format: Literal["count", "percent", "duration_s"]
    value: float | None             # None = not available (see `unavailable`)
    unavailable: str | None = None  # the reason, e.g. "Instagram insights aren't granted for @shop"

class MetricDelta(ResponseModel):
    current: MetricValue
    previous: MetricValue
    change_pct: float | None        # computed by the service; None when either side is None or 0
    direction: Literal["up", "down", "flat"] | None
    tone: Literal["good", "bad", "neutral"]  # from the metric's "higher is better" rule

class Period(ResponseModel):
    start: date
    end: date                       # inclusive
    label: str                      # from timeparse, e.g. "1–23 Oct" / "this month"
    days: int

class MetricComparisonVisual(ResponseModel):
    kind: Literal["metric_comparison"]
    version: Literal[1] = 1
    title: str
    current: Period
    previous: Period
    comparable: bool                # False if the periods differ in length (stated in the UI)
    metrics: list[MetricDelta]      # max 8
    account_ref: AnswerRef | None = None

class TrendVisual(ResponseModel):
    kind: Literal["trend"]
    version: Literal[1] = 1
    title: str
    metric: MetricValue             # value = the period total, or None
    granularity: Literal["day", "week"]
    points: list[TrendPoint]        # max 92; TrendPoint{date, value: float | None}

class RankedPostsVisual(ResponseModel):
    kind: Literal["ranked_posts"]
    version: Literal[1] = 1
    title: str
    metric: MetricValue
    period: Period
    considered: int                 # sample size
    items: list[RankedPostRow]      # max 10; {post_id, label, format, thumbnail_url?, value, ref}

class SentimentVisual(ResponseModel):
    kind: Literal["sentiment_summary"]
    version: Literal[1] = 1
    title: str
    period: Period | None
    positive: int
    neutral: int
    negative: int
    not_analysed: int
    topics: list[TopicCount]        # max 6

class LeadListVisual(ResponseModel):
    kind: Literal["lead_list"]
    version: Literal[1] = 1
    title: str
    total: int
    items: list[LeadRow]            # max 10; {contact_id, name, platform, lead_score,
                                    #   last_activity_at, reason, ref (conversation)}
    more_route: str | None = None   # workspace-relative, checked by SAFE_PATH on the web

class TableVisual(ResponseModel):
    kind: Literal["table"]
    version: Literal[1] = 1
    title: str
    columns: list[TableColumn]      # max 6; {key, label, align, format}
    rows: list[dict[str, str | float | None]]  # max 10; values typed by column format
    total: int
    more_route: str | None = None

Visual = Annotated[
    MetricComparisonVisual | TrendVisual | RankedPostsVisual | SentimentVisual
    | LeadListVisual | TableVisual,
    Field(discriminator="kind"),
]
```

Notes:
- **Types:** `kind` has no default, so the OpenAPI discriminator works (the comment at `schemas/agent.py` line ~134). Every list is capped in the type, which keeps the payload bounded.
- **Strings:** all strings are server-written or tool-provided labels. Fields that carry customer text (post `label` from a caption, a lead `name`, a topic `label`) are `clip`ped like today's tool text, and marked in a docstring as "untrusted: render as text".
- **Links:** routes are workspace-relative and validated by the web's `actionPath` rules (`SAFE_PATH`). Refs reuse `AnswerRef` (add the kinds `contact` and `account` for leads and accounts).

## 3. TypeScript (generated, then aliased)

```ts
// web/lib/api/types.ts
export type Visual = AgentRun["visuals"][number];
export type VisualKind = Visual["kind"];

// web/components/agent/VisualView.tsx
export function VisualView({ visual }: { visual: Visual }) {
  switch (visual.kind) {
    case "metric_comparison": return <MetricComparison visual={visual} />;
    case "trend":             return <TrendChart visual={visual} />;
    case "ranked_posts":      return <RankedPosts visual={visual} />;
    case "sentiment_summary": return <SentimentSummary visual={visual} />;
    case "lead_list":         return <LeadList visual={visual} />;
    case "table":             return <DataTableVisual visual={visual} />;
    default:                  return assertNever(visual); // unknown kinds: see section 6
  }
}
```

## 4. Computation rules (server, never the model or the browser)

- **Percentage change:** `change_pct = (current − previous) / previous × 100`, rounded to 1 decimal. It's `None` when either side is `None` or `previous == 0` (the card shows "new", not ∞).
- **Direction:** `flat` when |change| < 0.5%. **Tone** comes from a per-metric table (`unfollows` up is bad).
- **Comparable periods:** "this month vs last month" compares **the same number of days**. When it's 23 October, that's 1–23 October against 1–23 September, using `timeparse`'s partial-period rule. `comparable=False` with the reason when the periods can't be matched (for example, the account was connected mid-period).
- **Missing data:**
  - A day with no snapshot is a gap, never a zero.
  - A metric that needs insights without the permission is `value=None` with the reason.
  - A period total of a metric that has gaps sums the known days and says "N of M days".
- **Rates** (engagement, reply rate) are computed in the service from counts, with the denominator shown in the hint.
- **Provenance:** every visual comes from exactly one tool step. `run_out` keeps the step order, and the step's `refs` give the citation. The web can show "From: Compare periods · @shop" via the step label.

## 5. Streaming and events

- **v1:** visuals arrive with the finished run (`GET /agent/runs/{id}` after `agent.completed`), as answers do today. No change to the SSE stream: events must stay content-free (they're shared with the workspace and capped at 64 KB).
- **v2 (progressive):**
  - When an `agent.step` event reports a successful step, the requester's client refetches the run detail.
  - The detail endpoint returns `visuals` built from the steps finished so far, so a visual appears before the prose is ready.
  - It needs no new event type. It costs one extra GET per visual-producing step.

## 6. Validation, versioning, fallback

| Concern | Rule |
|---|---|
| Validation on write | Pydantic validates each visual when the tool builds it. A builder error fails **only the visual** (logged, `visual=None`); the tool result and the answer stand |
| Validation on read | `run_out` re-validates the stored `visual` with the current model. An invalid one (from an older version) is dropped, with a metric counter |
| Versioning | `version` on each visual. A breaking change adds a new `kind` or version, and the web keeps rendering the old version until runs older than the 180-day retention are gone |
| Unknown kind on the web | Can't happen with the generated union. During a deploy where the API is ahead of the web, render nothing for that visual. The prose and the sources still stand |
| Render error | Each `VisualView` is wrapped in an error boundary that hides the visual and logs to Sentry. The text answer is the fallback |
| Partial runs | Visuals come only from successful steps. A `partial` run shows what it has |
| Size | Each visual ≤ 8 KB serialised (test-enforced), and ≤ 3 per run |

## 7. Errors and "not available" (the contract with the prose)

The tool's `caveats` keep reaching the model as they do now, so the prose explains missing data. The visual carries the same reasons in `unavailable`. Both come from one server string, so they can't disagree.
