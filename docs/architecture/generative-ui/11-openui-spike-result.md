# 11 · OpenUI spike result (VIS-14)

Offline spike against the decision gate in doc 07 (phase 4). Nothing here ships. Run on 2026-10-25 on the scratch branch `spike/openui` (folder `spike/openui/`, not part of `apps/web`; `apps/web/package.json` and the lockfile were not touched).

## Recommendation

**Do not adopt OpenUI now. Keep decision C (doc 08).** Three of the four gate conditions pass in the spike, but the fourth, a real open-ended use the catalogue can't serve, is not there: every question in the eval set that has a chart is already served by a typed visual the API builds with no model tokens, no model latency and no way to get a number wrong. The one thing OpenUI would add, a model-written layout, has no product need yet. Re-run the harness (below) if one appears, for example "design me a dashboard" or a custom report, or when a model with a different profile is chosen.

| Gate (doc 07) | Result | Passes |
|---|---|---|
| Valid output at least 98% | 30 of 30 (100%); 6 of 6 for two-visual answers | Yes |
| Zero number errors | 0 of 361 numbers outside the tool result; 0 misplaced figures (current/previous, rank/value, sentiment counts). 0 of 160 in the two-visual probe | Yes, with the caveat below |
| Latency added at most 1.5 s at p95 | As a separate call: p95 1.54 s (run 1: 2.55 s, max 4.1 s). Written inside the answer's own turn: about 0.25 s for one visual, 0.56 s for two (estimate) | Only if written in the answer's turn; not measured there |
| A concrete use the catalogue can't serve | None found | **No** |

## What was built

- `spike/openui/lib.tsx`: the phase 1 visuals as OpenUI components with `defineComponent` and `createLibrary`: `MetricComparison` with `Metric`, `RankedPosts` with `RankedPost`, `SentimentSummary` with `Topic`, and a `Visuals` root. Props mirror `schemas/agent.py`. Only our own components are registered; `@openuidev/react-ui` is not installed.
- The prompt: `npx openui generate ./lib.tsx` (CLI 0.6.0) wrote `out/system-prompt.txt`, about 4 KB (about 1,000 tokens), with a short preamble and rules added through `PromptOptions` ("copy numbers exactly", "null when the tool gave none", "one component per tool result").
- `export_fixtures.py`: 30 scenarios taken from the agent eval set (`tests/evals/cases.py`): 5 `compare_periods`, 7 `top_posts`, 18 sentiment and topics (English, Hindi and Hinglish). The tool result of each is worked out from the eval seed's own declarations (no database): the same numbers the eval expects.
- `generate.py`: Gemini (`gemini-3.5-flash-lite`, the agent's model from the API settings, temperature 0.2 as the agent uses) gets the system prompt, the question and the tool result, and writes OpenUI Lang. The key is read through the API's `Settings` class and `apps/api/.env` and never printed or written.
- `validate.tsx`: parses with `createParser(library.toJSONSchema())`, renders with `Renderer` to static markup, then checks. Valid means a `Visuals` root, no validation errors, nothing unresolved or orphaned (the parser drops those silently), and it renders. Number fidelity: every number in the props, including numbers inside strings, must be one the tool result holds, and every figure must sit in its own slot.
- A probe for open-ended use: 6 questions made by joining two eval questions ("... And also: ...") with both tool results, to see whether the model composes a two-part layout.
- `OPENUI_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` were set for every install and CLI run.

## Numbers (final run)

| | 30 single-visual questions | 6 two-visual questions |
|---|---|---|
| Valid | 30 (100%) | 6 (100%) |
| Right component for the tool | 30 | 6 |
| Numbers written / not in the tool result | 361 / 0 | 160 / 0 |
| Figures in the wrong slot | 0 | 0 |
| Input tokens per call (prompt, question and tool result) | about 1,130 | about 1,380 |
| Output tokens per call | about 119 (most 207) | about 266 (most 349) |
| Latency p50 / p95 / max, separate call | 1.24 / 1.54 / 1.91 s | 1.57 / 1.74 / 1.74 s |

Across the 36 calls, time was about 1.0 s fixed plus about 2.1 ms per output token. So the same Lang written inside the answer's own last turn would add about 0.25 s (120 tokens) or 0.56 s (270 tokens) to it, plus the prompt's 1,000 tokens in every turn that can draw a visual. That is an estimate from the slope, not a measurement in the agent loop.

Cost: the whole spike, with its reruns after harness fixes, made about 140 Gemini calls of roughly 1,100 input and 120 output tokens: on the order of 150,000 input and 15,000 output tokens. In use, one visual answer costs about 1,130 input and 120 output tokens more than today, where a visual costs none.

Run to run, latency moves: an earlier run of the same 30 questions (before the prompt rule for several visuals) had p95 2.55 s and a worst call of 4.1 s. A p95 gate on 30 samples is noisy; treat 1.5 s as borderline for a separate call.

## What the numbers don't show

- **Fidelity is copying, not working out.** The tool result sat in the same prompt and the model only had to copy numbers across. Zero errors in 521 numbers is good, but production would still need a runtime check that every figure in a model-written visual is in a tool result (the spike's `validate.tsx` is that check). Today's builders get this by construction.
- **One model, one temperature, small tool results.** `gemini-3.5-flash-lite` at 0.2 with results of at most a few KB. Larger lists (10 leads, 10 table rows, 92 trend points) would cost more tokens and more chances to drop a row.
- **No open-ended layout was asked for.** The probe composes known components. It shows composition works; it doesn't show a need.
- **Honest on missing data.** With the null result fed in by a harness mistake (a probe run with the tool result missing), the model wrote an empty `Visuals([])` or a "data unavailable" card rather than inventing numbers. Worth knowing; not a reason to adopt.

## Findings about the library

- **Installed and ran without trouble** (2026-10-25): `@openuidev/react-lang` 1.0.1, `@openuidev/lang-core` 1.0.1, `@openuidev/cli` 0.6.0, `react` 19.3.1, `zod` 4.6.7, `tsx` (the harness only); 77 packages, 95 MB, in the throwaway folder. `lang-core` has an install-time telemetry script; the environment variables above turn it off.
- **A nullable prop is a required argument.** With `z.number().nullable()` the generated signature marks the prop required (`current*`) and the parser rejects a `null` for it: the first attempt was 0 of 30 valid for that reason alone. `.nullish()` makes it optional. This is a trap in the library definition, not a model fault, and the kind of thing that costs time every time the catalogue changes.
- **Two sources of truth.** Component props are written twice (Pydantic in the API, zod for OpenUI) and the prompt must be regenerated whenever either changes. Doc 02 already named this.
- **The parser is forgiving in ways that hide loss.** Unreferenced statements are dropped without an error (`meta.orphaned`); the harness counts them as invalid. A production renderer would need the same check.
- `@openuidev/react-ui` (0.x, many dependencies) was not needed; `react-lang` and `lang-core` alone were enough.

## Harness mistakes found and fixed on the way

These changed the numbers, so they are recorded: the JSX runtime was not configured (render threw, 0 of 30 valid); nullable props were required (above); the number check read digits from statement ids such as `topic4` (38 false "not in the result" hits); a two-visual probe ran once with the tool results missing from the prompt. After the fixes the 30 questions were generated again from scratch with the final prompt; the figures above are from that run.

## To run it again

From the `spike/openui` folder of the scratch branch (`npm install` with `OPENUI_TELEMETRY_DISABLED=1`), then:

1. `npx openui generate ./lib.tsx --out out/system-prompt.txt --no-interactive --no-telemetry`
2. In `apps/api`, with dummy `DATABASE_URL`, `DATABASE_URL_DIRECT` and `REDIS_URL` and `SPIKE_ENV_FILE` pointing at the API's `.env`: `uv run python ../../spike/openui/export_fixtures.py ...`, then `generate.py`.
3. `node --import tsx validate.tsx out/fixtures.json out/generations.json out/report.json`

Outputs of the final run are committed on `spike/openui` under `spike/openui/out/` (fixtures, generations, reports; no key).

## Decision

VIS-14 is done as a spike. Keep decision C. Revisit only with a concrete open-ended use, and then run the harness again on that use with real tool results from the eval workspace, a runtime number check, and the call written inside the agent's own turn so the added latency is measured there.
