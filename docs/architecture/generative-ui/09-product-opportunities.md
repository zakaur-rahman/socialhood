# 09 · Product opportunities

Ways visual, interactive answers could make Social Hood more useful, beyond basic charts. They're ranked by customer value, effort, reliability and differentiation. **Effort:** XS to XL, relative. **Reliability:** how much rests on deterministic data (high) as against model judgement (low).

| Rank | Opportunity | What the member gets | Value | Effort | Reliability | Differentiation | Depends on |
|---|---|---|---|---|---|---|---|
| 1 | **"Who needs me now" lead cards** | Asking "who should I reply to?" returns the 10 hottest unanswered people, each with lead score, what they asked, how long they've waited and one tap to open the chat with a draft ready | Very high: revenue that's otherwise lost | M | High (lead score, waiting time and drafts exist) | High: most tools stop at an inbox | VIS-08, `draft_reply`; GR-18 for stages |
| 2 | **Period comparisons with evidence** | "This month vs last" as KPI cards plus the posts that drove the change, each linked | High: the question every owner asks | M (phase 0 data) | High | Medium | VIS-01 to VIS-05 |
| 3 | **Drill-down from a number to the records** | Tap "comments −9%" to see the comments, or "negative 23%" to see those comments in Comments | High: turns a number into action | S–M per link | High (routes and filters exist) | Medium | VIS-05, Comments filters |
| 4 | **Weekly marketing report page** | A shareable page (and the existing digest email) with the same cards, top posts, sentiment and leads, linked from Ask | High for agencies and owners | M–L | High | Medium-high (built on our own data) | VIS-13, GR-34 |
| 5 | **Contextual automation setup** | "People keep asking about price" shows the count, examples, and a ready automation draft card. The insight leads straight to the fix | High: cuts setup time | S (draft card exists; add the evidence visual) | Medium (topic detection) | High | `comment_topics`, `prepare_automation` |
| 6 | **Cross-channel customer timeline** | "Tell me about Priya" shows a timeline of DMs, comments, story mentions, automation runs, consent and tags | Medium-high for teams | M | High (contacts GR-02, runs, mentions GR-07) | Medium | GR-17 contact drawer |
| 7 | **Recommendations with measurable outcomes** | "Post more Reels" offered only when the data shows it, with the evidence chart and a check-back ("Reels since: +12% reach") | Medium-high | L | Medium: rules must be conservative | High | VIS-07, a rules service |
| 8 | **Activity and failure answers** | "Why didn't my automation send?" shows the failure, its plain reason and the one-fix button (GR-05's feed) | Medium: trust | S (Activity exists, `list_recent_failures` tool exists) | High | Medium | GR-05 |
| 9 | **Interactive analytics exploration** | Range and platform toggles on any visual (re-asks the agent) | Medium | M | High | Low-medium | VIS-11 |
| 10 | **Open-ended dashboards** ("build me a campaign dashboard") | Model-composed layouts | Uncertain | L–XL | Low (model layout) | Medium | The OpenUI spike (VIS-14) gate |

**Recommended next five** after the MVP, in order:
1. lead cards (1);
2. drill-down links (3);
3. contextual automation setup (5);
4. failure answers (8);
5. the weekly report page (4).

They reuse data and screens we already have, and each one turns an answer into the action that follows it.
