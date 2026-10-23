# 04 · Generative UI design

What the member sees, which components draw it, and how an answer chooses between prose, charts, tables and actions. It builds on the recommendation in doc 03: visuals are typed, server-derived, and rendered with our own components.

## 1. Principles

1. **The answer leads, the evidence follows.** One or two sentences that answer the question, then the visual that proves it, then the details on request.
2. **The service computes every number,** including every change and percentage. The model chooses which tools to run and writes the prose; it never authors a figure in a visual.
3. **The visuals fit the panel.** The Ask panel is a side sheet, about 400 px or wider and resizable (UI-078), with a full Ask page. Every visual works at 375 px. No answer renders more than 10 rows; past that, link to the screen that owns the data.
4. **Buttons do one of two things.** They open an existing screen with a hand-off (as action cards do), or they call an existing authenticated API with the member's own token. A visual never carries power of its own.
5. **Show nothing rather than something wrong.** When data is missing (insights not granted, not enough history, no analysed comments), the visual shows that state with the reason; it's never zeros.
6. **Same look as the rest of the app:** tokens, `Card`, `MetricTile`, `SentimentBar`, `Table`, `EmptyState`, the copy lint and the design lint. No second design system.

## 2. How an answer chooses its shape (response selection)

The **tools the model ran** decide the visual, not the model's wording. Server rules map each tool result to at most one visual. The web shows a run's visuals in order, and never more than three; with more, the rest go into the step disclosure.

| Question type | Prose | Visual | Rule |
|---|---|---|---|
| Conceptual ("what's a good reply rate?", "how do I…") | Short answer | None | Visuals only come from tools with chartable data |
| Numeric comparison of two periods ("this month vs last") | One or two sentences: the biggest changes | `MetricComparison` (KPI cards with change), optionally a `ComparisonChart` | `compare_periods` (new, doc 07) |
| Trend over time ("how has reach moved?") | One sentence | `TrendChart` | `metric_trend` (new) |
| Ranking ("best posts", "top 10") | One sentence on what wins | `RankedPosts` (`DataTable` rows with thumbnails), max 10 | `top_posts` |
| One post against its usual ("how did yesterday's reel do?") | One sentence | `PostComparison` (reuses `PostPerformanceCard`'s figures) | `post_performance`, `compare_posts` |
| Sentiment ("what are people saying?") | One or two sentences, and the topics | `SentimentSummary` (split bar plus top topics) | `sentiment_distribution`, `comment_topics` |
| Leads ("who hasn't had a reply?") | One sentence | `LeadList` (max 10 rows, each with an Open action) | `list_contacts` with filters (lead tools later, GR-18) |
| Create or change something ("make an automation for pricing questions") | One sentence | Existing **action card** (opens the editor with the draft) | draft tools, unchanged |
| Data unavailable | The reason, from the tool's caveat | The visual's empty or unavailable state, or none | caveats |
| Complex analysis ("why has engagement dropped?") | A short summary of what the data shows (no speculation) | Up to three visuals from the tools it ran, in order | Several tools |

## 3. Component catalogue

"Reuse" names the existing code to build on (doc 01, section 6). Every visual is a **deterministic** component. The column "OpenUI later?" says whether it's a good candidate to register with `defineComponent` if we ever try the hybrid (doc 03, D).

| Component | Purpose | Data (props) | States | Accessibility | Responsive | Interaction | Reuse | OpenUI later? |
|---|---|---|---|---|---|---|---|---|
| `MetricCard` | One figure with an optional change | `label`, `value: number\|null`, `format` (count, percent, duration), `change?: {pct, direction, tone}`, `hint?` | Value; "not available" with reason; skeleton | Change has screen-reader words (as `TrendChip`) | 2 per row at 375, 4 at ≥768 | Optional link to the owning screen | `home/MetricTile`, `TrendChip` | Yes |
| `MetricComparison` | Current period against the previous period for several metrics | `current: Period`, `previous: Period`, `metrics: MetricDelta[]` | Partial: a metric with no data shows "not available"; period labels always shown | Table semantics (caption = periods) | A grid of `MetricCard` | Period labels; no controls in v1 | `MetricTile`, `home/format` | Yes |
| `ComparisonChart` | Bars for two periods per metric | `series: [{label, current, previous}]` | Hidden when fewer than 2 metrics have values | `role="img"` plus a full aria-label, with the table available as text | Horizontal bars (fit narrow widths) | None | `TopIntentsCard` bars on tokens | Yes |
| `TrendChart` | A metric by day or week | `points: [{date, value\|null}]`, `metric`, `granularity` | Gaps for missing days; "not enough history" under 3 points | `role="img"` + aria-label summarising the start, end, minimum and maximum; data table in the disclosure | Full width, 120 px tall | Hover or tap shows the value (v2) | `TrendLine` grows into a labelled SVG line | Yes |
| `BreakdownChart` | Shares of a whole (format, platform, intent) | `parts: [{label, value}]` | Empty | `role="img"` plus a legend | Stacked bar plus legend | None | `SentimentBar` pattern | Yes |
| `DataTable` | A small tabular result | `columns: [{key, label, align, format}]`, `rows`, `total`, `more_href?` | Empty row text; "+N more" link | `Table` caption; keyboard scroll | Horizontal scroll (`scrollLabel`) | Client-side sort on a column in v2; never server paging in the answer | `ui/table` | Yes |
| `RankedPosts` / `PostPerformanceCard` | Ranked posts with thumbnail, metric and age | `items: [{post_id, label, thumbnail_url?, metric, value, permalink?}]`, `metric`, `considered` | "Not enough posts"; thumbnail fallback | Each row is a link to the post's page; image alt is the post label | One column at 375 | Row opens `comments/{post_id}` | `PostThumb`, `TopPostsCard` | Yes |
| `PostComparison` | One post against its baseline | `post`, `metrics: [{label, value, baseline, diff_pct}]`, `baseline_text` | "Too young to compare" (`youngerNote`) | As `PostPerformanceCard` | Stack | Link to the post | `PostPerformanceCard`, `lib/analytics/format` | No (an existing card) |
| `SentimentSummary` | Split plus topics | `positive`, `neutral`, `negative`, `not_analysed`, `topics: [{label, count}]` | "No analysed comments yet" | Bar `role="img"`, legend text | Stack | Topic opens Comments filtered (v2) | `SentimentBar`, `SentimentLegend`, `TopicsCard` | Yes |
| `LeadCard` / `LeadList` | People to follow up with | `items: [{contact_id, name, platform, lead_score, last_activity_at, reason, conversation_id}]` | Empty: "Nobody waiting" | Each card is one link with full text | One column | **Open** goes to the conversation (hand-off); no inline status change until GR-18's API exists | `inbox/ConversationRow` look, `avatar`, `lib/ui/identity` | Yes |
| `InsightCard` | One stated finding with its evidence ref | `title`, `body`, `ref?` | None | Plain text | Full width | Citation pill | `AnswerText` citations | No: insights stay in prose (model-written) |
| `RecommendationCard` | A suggested next step tied to data | `title`, `why`, `action?: ActionCard` | None | Plain text | Full width | Its action card | `ActionCardView` | No (v2, only from deterministic rules) |
| `ReportSummary` | Header of a generated report | `title`, `period`, `sections[]` | Generating; failed | Heading structure | Full width | Download or share (later) | `Card` | No (reports are a page, doc 09) |
| `DateRangeFilter` | Change the period of a visual | `range`, `options` | None | ToggleGroup semantics | Wraps | **Asks again** (sends a follow-up with the new range), never queries directly | `RangeControl` | No (v2) |
| `PlatformFilter` | Instagram, WhatsApp (Facebook later) | `platforms` | None | ToggleGroup | Wraps | As above | `toggle-group` | No (v2) |
| `AutomationConfig` | Draft automation preview | The existing `AutomationDraftAction` prefill | Existing | Existing | Existing | **Open in editor** (existing hand-off) | `ActionCardView`, automation editor | No: keep the card |
| `ActionPanel` | Group of actions under an answer | `ActionCard[]` | None | Buttons with full labels | Stack | Each is a hand-off | `ActionCardView` | No |
| `ApprovalPanel` | Approve or reject an agent write | R2: `AgentApproval` | Pending, approved, expired | Focus management, confirm | Sheet | Calls `POST /agent/approvals/{id}/approve` (R2) | None yet (R2) | No: never model-authored |

**Rules for every component:**
- **States:** a loading skeleton only while the run is active. Every component has an "unavailable" state that shows the tool's caveat. Empty states use `EmptyState` with copy from `lib/copy.ts`.
- **Colour:** only the four chart aliases. Two periods use `chart-series-1` for current and `chart-neutral` for previous, so no new hue is needed (C-075). A true second series colour is a design decision (doc 08).
- **Text:** labels come from the server. Model text never goes inside a visual; customer text (post captions, names) renders as plain text.
- **Language:** answers may be Hindi or Hinglish, but labels come from tools in English for v1. Localising them is out of scope and noted (doc 08).

## 4. Interactive actions

- **v1, unchanged:** action cards open the existing screen with a hand-off, and the member completes the action there (`web/lib/agent/handoff.ts`). This covers drafting a reply, scheduling a message, replying to a comment and creating a draft automation.
- **v1, new:** navigation from visuals. A post row opens the post, a lead opens the conversation, and "+N more" opens the owning screen. All targets go through `actionPath`'s `SAFE_PATH`.
- **v2:**
  - **Filter controls** (range, platform) send a follow-up question with structured hints, so the agent runs again with the same rules. No direct data query from a visual.
  - **"Update lead status"** waits for GR-18's API, then calls it with the member's token, with confirmation.
- **R2:**
  - `ApprovalPanel` for agent writes goes through the planned gateway (`agent/gateway.py`): policy, role, limits, confirmation, idempotency key, and a time-to-live.
  - A button sends only a server-issued approval id, never a payload the model wrote.

## 5. Reports

| Report | Form | Why |
|---|---|---|
| "How did this week go?" in Ask | An interactive answer: `MetricComparison`, plus `RankedPosts` and `SentimentSummary` | Same components, no new surface |
| Weekly marketing report | **A page plus an email** (the digest exists: `notify/digest.py`; GR-34 plans trends plus a weekly report) | Shareable, linkable, rendered from the same services |
| Campaign or agency executive summary | A downloadable PDF from the report page (later) | Agencies forward it; it isn't a chat artefact |
| Lead follow-up report | The Leads view (GR-18) | Needs a working list, not a one-off answer |

**Rule:** chat answers are for questions. Anything a member returns to or shares is a page built from the same services and components.

## 6. Example flows

**"Compare my Instagram performance this month versus last month"**
1. `timeparse` resolves "this month" (1 Oct to today) and "last month" (September).
2. The model calls `compare_periods(metrics=[reach, views, interactions, followers, comments], range_a="this month", range_b="last month", account=@shop)`.
3. The service reads `account_daily_metrics` and comment counts, and computes the totals and percentage change for each metric, comparing partial with partial: the same number of days. A metric with no data in either period is `null` with a reason.
4. The tool returns the result plus `visual: metric_comparison`.
5. The model writes: "Reach is up 18% on the same days of September, but comments fell 9% [1]."
6. The web shows the sentence, then `MetricComparison` (5 cards), then sources.

**"Show my best-performing posts this month"** → `top_posts(range="this month", metric="engagement", n=10)` → visual `ranked_posts` → a 10-row table with thumbnails, each opening the post.

**"Analyze the sentiment of my comments"** → `sentiment_distribution(range)` and `comment_topics(range)` → visual `sentiment_summary` → split bar and topics. If 40% aren't analysed yet, the visual says so.

**"Find leads who haven't received a reply"** → `list_contacts(min_lead_score=60, awaiting_reply=true, n=10)` (a filter to add) → visual `lead_list` → cards, each opening the conversation.

**"Create an automation for people asking about pricing"** → `prepare_automation` → the existing action card → the editor opens with the draft. No change.

**"Why has engagement dropped?"** → `compare_periods`, then `top_posts` for both periods → up to two visuals. The prose states only what the data shows ("fewer Reels: 3 against 8"), and the prompt already forbids guessing causes.

**"What's a good reply rate?"** → no tool, no visual, two sentences.

**Data unavailable ("compare reach" without the insights permission)** → `compare_periods` returns reach `null` with the caveat "Instagram insights aren't granted for @shop". The card says "Not available", and the prose says why.
