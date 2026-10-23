# 07 · Implementation roadmap

The phases from nothing to visual answers, then the optional OpenUI evaluation. Each phase ships on its own and is useful alone. Task ids refer to doc 10.

## Phase 0 · Data that visuals need (prerequisite)
Every option needs this, OpenUI included. Today no service can answer "this month against last month" (doc 01, section 3).

- **VIS-01:** an analytics service and route to read `account_daily_metrics` (sums, comparable periods, gaps), plus `compare_periods` and `metric_trend` in `services/analytics/`.
- **VIS-02:** agent tools `compare_periods` and `metric_trend` (read, agent role), with eval cases for "this month vs last month", "last 7 days vs the 7 before" and "how has reach moved".
- **Acceptance:**
  - The eval's month-over-month answers match seeded truth.
  - The prose never states a change the tool didn't return.
  - Insights-not-granted produces caveats, not zeros.

## Phase 1 · Visual contract and the first three components (MVP)

- **VIS-03:** the `Visual` union and its builders (doc 05), on `compare_periods`, `top_posts` and `sentiment_distribution`.
- **VIS-04:** `run_out` projection, dropping visuals from `model_view`, the `agent_visuals` flag, and the regenerated client.
- **VIS-05:** the web `VisualView` with an error boundary, plus `MetricComparison` (from `MetricTile`), `RankedPosts` (from `PostThumb` and `Table`) and `SentimentSummary` (from `SentimentBar` and `TopicsCard`).
- **VIS-06:** tests (doc 06, section 3) and an e2e spec: ask "compare this month with last month" in the sandbox and see the cards.
- **Acceptance:**
  - On the internal pilot, comparison, top-posts and sentiment questions show the right visual, with numbers identical to the tool result.
  - No visual appears on conceptual questions.
  - The answer is unchanged with the flag off.

## Phase 2 · Trends, leads and tables
- **VIS-07:** `TrendChart`, a labelled SVG line built from `TrendLine`. It needs a decision on a second series colour, or uses current against neutral.
- **VIS-08:** `LeadList` on `list_contacts` with an "awaiting reply" filter, opening the conversation.
- **VIS-09:** a generic `DataTable` visual with "+N more" routes.
- **VIS-10:** progressive visuals: refetch the run detail when a visual-producing step finishes.

## Phase 3 · Interactions
- **VIS-11:** range and platform controls on visuals, asked as a structured follow-up (re-runs the agent; no direct querying).
- **VIS-12:** a "Prepare a reply to these leads" action, giving a draft card per lead via the existing `draft_reply`.
- **VIS-13:** weekly report page (GR-34) built from the same services and components, with a link from the answer.

## Phase 4 · Optional OpenUI evaluation (decision gate)
- **VIS-14:** an offline spike, not shipped.
  - Describe the Phase 1 components with `defineComponent`.
  - Generate the prompt with the CLI.
  - Have Gemini write OpenUI Lang for 30 eval questions.
  - Measure valid-parse rate, number fidelity against tool results, latency and tokens.
- **Gate:** adopt the hybrid (doc 03, D) only if valid output is at least 98%, there are zero number errors, the latency added is ≤ 1.5 s at p95, and there's a concrete use that the catalogue can't serve.

## Model strategy, performance and cost

| Approach | Extra model calls | Extra tokens per run (estimate) | Extra latency (estimate) | Reliability |
|---|---|---|---|---|
| **Server-derived visuals (recommended)** | 0 | Negative: visuals are dropped from `model_view` | ≈ 0 (builders run in the tool, < 10 ms) | Highest |
| Same model writes OpenUI Lang | 0 | Component prompt (~0.5k–2k input) on **every** turn, plus Lang output (vendor claims ~50% less than JSON UI) | Output time for the layout at Flash-Lite speed | Unmeasured for Gemini |
| Agent plus a small presentation model | +1 per answer | That call's input (results) plus output | +1 model round-trip (≈1–3 s typical for a Flash-class model; to measure) | Two failure points |
| Hybrid (selective OpenUI) | 0 or 1, only where used | As above, only where used | As above, only where used | Mixed |

These are estimates from stated assumptions, not benchmarks. Today's eval log shows an average answer time of 3.7 s and p95 7.4 s on `gemini-3.5-flash-lite` (agent.v2).

**Caching:**
- Visuals need no cache: they come from stored steps.
- Analytics service results may be cached **per workspace and range** for the time window of the underlying snapshot job (daily metrics change once a day), keyed by workspace id. Never cross users' private data.
- Don't cache answers.

**Avoiding waste:**
- Reuse the tool result for the visual, never a second query.
- No visual for conceptual answers.
- Cap 3 visuals per run, 10 rows each.
- The text fallback always ships.

## Evaluation plan (pilot)

| # | Scenario | Expected tools | Expected visual | Data checks | Security checks | Fallback |
|---|---|---|---|---|---|---|
| 1 | Compare Instagram this month vs last month | `compare_periods` | `metric_comparison` | Every delta equals the service's; comparable days | Own workspace only | Caveat cards when insights aren't granted |
| 2 | Top 10 posts this month | `top_posts(n=10)` | `ranked_posts` | Order and values match; `considered` shown | Links pass `SAFE_PATH` | "Not enough posts" |
| 3 | Comment sentiment | `sentiment_distribution`, `comment_topics` | `sentiment_summary` | Counts add up; not-analysed shown | Captions rendered as text | "No analysed comments yet" |
| 4 | Instagram vs WhatsApp (or vs Facebook) | `compare_periods` by platform | `metric_comparison` | Per-platform totals | | Facebook: "not connected" text (GR-29) |
| 5 | Leads needing follow-up | `list_contacts(awaiting_reply)` | `lead_list` | Lead scores from the database | Agent-role sees allowed data only | "Nobody waiting" |
| 6 | Weekly report | Several | Up to 3 visuals plus a link to the report page | As above | | Text summary |
| 7 | Create an automation | `prepare_automation` | Action card (unchanged) | Prefill matches | No write without the member | Card opens the editor |
| 8 | Draft a customer reply | `draft_reply` | Action card | Draft states only known facts | Injection-seeded DM ignored | Text draft |
| 9 | Conceptual question | none | none | | | |
| 10 | Analytics with no data (new account) | `compare_periods` | Cards "not available" | No zeros | | Prose explains |

**Measures:**
- **Speed:** time to the first visible response (the run's working steps), time to the complete render (`completed_at` → visual painted).
- **Quality:** render success rate (boundary hits ÷ visuals), invalid-visual rate (dropped on write or read), displayed-number accuracy (eval).
- **Cost:** unnecessary LLM calls (should be 0 added) and added credits per run (should be 0).
- **Use:** interaction success (clicks on visual links), mobile layout at 375 px (ui-shots), and accessibility (axe).

**Pilot:**
1. Flag on for internal workspaces for two weeks.
2. Then 10% of workspaces with an Instagram insights grant.
3. Compare follow-up rate and "copy answer" use with and without visuals.
4. Then everyone.

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Insights permission still pending (App Review) | Reach and views are unavailable for most accounts | Show likes, comments and messages first; clear "not available" states |
| Account daily metrics have gaps | Misleading totals | "N of M days" and the comparable-days rule |
| One series colour | Two-series charts look alike | Current = brand, previous = neutral; propose a second hue (doc 08) |
| Hindi or Hinglish answers with English labels | Mixed languages | Accept for v1; localise labels later |
| Scope creep into a dashboard | A second analytics product inside chat | Rule: chat answers questions; pages hold dashboards (doc 04, section 5) |
