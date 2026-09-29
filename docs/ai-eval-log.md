# AI evaluation log (TR-AI-10)

Run the harness before changing a model or a prompt version, and record the result here, newest
first. No change may regress a result by more than 3 points (§2.13).

```sh
cd apps/api
uv run python -m tests.ai_eval.run --markdown   # prints the row to paste below
```

Targets (PRD §1.2): intent accuracy ≥ 85% and sentiment accuracy ≥ 90% on the owner's 300 labelled
messages; no fabricated facts in suggestions (T5.4). Tune `AI_RETRIEVAL_MIN_SIM` and
`AUTO_MIN_CONFIDENCE` from these runs (T5.9).

Datasets: `apps/api/tests/ai_eval/messages.jsonl` and `suggestions.jsonl`. They hold synthetic
placeholders until the owner's labelled set replaces them; results on placeholders are not a
baseline.

| Date | Model | Prompts | Intent accuracy | Sentiment accuracy | needs_human recall | Fabrication rate | Auto-policy pass rate | Notes |
|------|-------|---------|-----------------|--------------------|--------------------|------------------|-----------------------|-------|
