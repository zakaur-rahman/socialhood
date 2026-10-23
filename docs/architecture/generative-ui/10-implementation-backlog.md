# 10 · Implementation backlog

Actionable tasks for visual answers (doc 08's decision C). Effort is relative (XS to XL). Paths: `api/` = `apps/api/src/socialhood/`, `web/` = `apps/web/src/`.

## Phase 0 · Data the visuals need

| ID | Task | Files | Depends | Priority | Effort | Acceptance criteria | Tests | Risks |
|---|---|---|---|---|---|---|---|---|
| VIS-01 | Account metrics read path: daily series, period sums and comparable-period comparison over `account_daily_metrics`, plus comment and message counts per period; a route `GET /analytics/account-metrics` | `api/services/analytics/account_metrics.py` (new), `api/repositories/analytics.py`, `api/api/v1/analytics.py`, `api/schemas/analytics.py` | none | P0 | M | Sums, gaps ("N of M days"), comparable days, `None` without insights, change % computed in the service | Unit (maths, gaps, zero), integration (route, tenancy) | Snapshot gaps; insights not granted for most accounts until App Review |
| VIS-02 | Agent tools `compare_periods` and `metric_trend` (read, agent role), using `timeparse` ranges | `api/agent/tools/analytics.py`, `tests/unit/test_agent_tools_registry.py` | VIS-01 | P0 | S | The model can answer "this month vs last month" with figures from the tool; the docstring's "not built" list updated | Integration (tools), eval cases ×6 (EN plus Hinglish), registry test | Prompt may still juxtapose `top_posts`; add eval coverage |

## Phase 1 · MVP: contract and three components

| ID | Task | Files | Depends | Priority | Effort | Acceptance criteria | Tests | Risks |
|---|---|---|---|---|---|---|---|---|
| VIS-03 | `Visual` union and builders (`metric_comparison`, `ranked_posts`, `sentiment_summary`); `visual` field on those result models | `api/schemas/agent.py`, `api/agent/tools/analytics.py`, `api/agent/visuals.py` (new builders) | VIS-02 | P0 | M | Each builder is a pure function of the tool's data; caps in types; ≤ 8 KB | Unit per builder (numbers, `None`, caps, size) | Schema churn; keep `kind` required |
| VIS-04 | `run_out` projection `AgentRun.visuals` (max 3, step order); drop `visual` from `model_view`; flag `agent_visuals`; regenerate the client | `api/services/agent_runs.py`, `api/agent/report.py`, `api/models/...` (flag), `apps/api/openapi.json`, `packages/api-client/schema.d.ts` | VIS-03 | P0 | S | Flag off gives an unchanged API; invalid stored visuals dropped on read | Integration (run detail and list, flag, tenancy, roles), contract CI | List payload growth; cap or omit in the list |
| VIS-05 | Web `VisualView` with an error boundary; `MetricComparison`, `RankedPosts`, `SentimentSummary` | `web/components/agent/VisualView.tsx`, `web/components/agent/visuals/*` (new), `web/components/agent/RunView.tsx`, `web/lib/api/types.ts` | VIS-04 | P0 | M | Renders at 375 px and in the panel; unavailable and empty states; links via `actionPath`; tokens only | Vitest (states, a11y with axe, malicious text), design lint, ui-shots | Palette (one series) |
| VIS-06 | E2E and eval: sandbox "compare this month with last month" shows cards; eval checks visual numbers | `apps/web/e2e/visuals.spec.ts`, `tests/evals/checks.py`, `tests/evals/cases.py` | VIS-05 | P0 | S | E2E green; eval number checks pass | E2E, eval | Sandbox needs seeded account metrics |

## Phase 2 · More views

| ID | Task | Files | Depends | Priority | Effort | Acceptance criteria | Tests | Risks |
|---|---|---|---|---|---|---|---|---|
| VIS-07 | `trend` visual and `TrendChart` (labelled SVG line, gaps, aria summary) | `api/agent/visuals.py`, `web/components/agent/visuals/TrendChart.tsx` | VIS-02, VIS-05 | P1 | M | Readable at 375; gaps shown; summary for screen readers | Unit, vitest, axe | Needs a second hue for two series (decision) |
| VIS-08 | `lead_list` visual on `list_contacts` with an `awaiting_reply` filter; `contact` ref kind | `api/agent/tools/conversations.py`, `api/services/contacts.py`, `api/schemas/agent.py` (`AnswerRefKind`), `web/lib/agent/routes.ts` | VIS-05 | P1 | M | Top 10 unanswered by lead score; each opens the conversation | Integration (filter, roles), vitest | GR-18 stages later |
| VIS-09 | Generic `table` visual with "+N more" route | `api/agent/visuals.py`, `web/components/agent/visuals/DataTableVisual.tsx` | VIS-05 | P2 | S | ≤ 10 rows, ≤ 6 columns, right-aligned figures | Unit, vitest | Overuse; keep it to tools with tabular data |
| VIS-10 | Progressive visuals: refetch run detail on a visual-producing `agent.step` | `web/lib/agent/cache.ts`, `web/lib/api/queries/agent.ts` | VIS-05 | P2 | S | Visual appears before the prose when its step finishes | Vitest (cache), e2e timing | Extra GETs; debounce |

## Phase 3 · Interactions and reports

| ID | Task | Files | Depends | Priority | Effort | Acceptance criteria | Tests | Risks |
|---|---|---|---|---|---|---|---|---|
| VIS-11 | Range and platform controls on visuals, asked as a structured follow-up (re-runs the agent) | `web/components/agent/visuals/*`, `web/components/agent/AskConversation.tsx`, `api/schemas/agent.py` (`AgentRunCreate.hints?`) | VIS-05 | P2 | M | Changing the range gives a new run with the same rules; no direct data query | Integration, e2e | Credit use per toggle (1 run each) |
| VIS-12 | "Prepare replies for these leads": a draft card per lead via `draft_reply` | `api/agent/tools/conversations.py`, web action cards | VIS-08 | P2 | S | Cards open each conversation with its draft | Integration, e2e | Draft quality; caps (8 tools) |
| VIS-13 | Weekly report page from the same services and components (GR-34), linked from answers | `web/app/(app)/w/[slug]/reports/*` (new), `api/services/reports.py` | VIS-01, VIS-05 | P2 | L | A shareable page per week; matches the digest email | Integration, e2e, ui-shots | Scope; align with GR-34 |

## Phase 4 · Decision gate

| ID | Task | Files | Depends | Priority | Effort | Acceptance criteria | Tests | Risks |
|---|---|---|---|---|---|---|---|---|
| VIS-14 | **Offline OpenUI spike** (not shipped): describe the phase 1 components with `defineComponent`, generate the prompt with the CLI, have Gemini write Lang for 30 eval questions, then measure valid rate, number fidelity, tokens and latency. `OPENUI_TELEMETRY_DISABLED=1` | A scratch branch only | VIS-06 | P3 | M | A written result against the gate (≥ 98% valid, 0 number errors, ≤ 1.5 s p95 added, a real open-ended use) | The spike's own harness | Package churn (react-ui 0.x); Gemini output quality |

## Cross-cutting (do alongside phase 1)

| ID | Task | Files | Priority | Effort | Acceptance criteria |
|---|---|---|---|---|---|
| VIS-X1 | Prompt: tell the model a visual will show the figures, so it keeps prose to the main change and doesn't repeat the table; prompt v3 with eval | `api/ai/prompts/agent.v3.md`, eval | P1 | S | Eval passes at ≥ v2's rate; answers shorter on visual questions |
| VIS-X2 | Quote or remove account display names in the system prompt (minor injection exposure) | `api/agent/context.py` | P1 | XS | Names passed as data, not instructions |
| VIS-X3 | Metrics and logs: `agent_visual` log line; counters for built, dropped and render-error | `api/services/agent_runs.py`, `api/observability/metrics.py`, web Sentry | P1 | XS | Visible in /metrics and Sentry |
| VIS-X4 | Design-system entries for the new components (charts §1.8, components §8) | `docs/ui-audit/DESIGN_SYSTEM.md` | P1 | XS | Documented with states and tokens |

**Critical path:** VIS-01 → VIS-02 → VIS-03 → VIS-04 → VIS-05 → VIS-06, which is the MVP: about two M and four S tasks plus tests.
