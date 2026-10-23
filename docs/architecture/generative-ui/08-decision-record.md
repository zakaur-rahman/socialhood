# 08 · Decision record: visual answers in Ask Social Hood

- **Status:** proposed (awaiting owner approval)
- **Date:** 2026-10-23
- **Related:** docs 01 to 07, `docs/agent-architecture.html`, C-075 (palette lock)

## Problem
Ask Social Hood answers with markdown text. Questions about performance, rankings, sentiment and leads produce long paragraphs and tables of numbers that are slow to read and easy to misread. We want charts, KPI cards, tables and safe action controls, without replacing the agent.

## Context
- **The agent:** Pydantic AI on Google Gemini (`gemini-3.5-flash-lite`), a non-streaming call, and a text answer with citations and action cards. Tools return typed results stored in `agent_steps.result` (doc 01).
- **The numbers rule:** the prompt forbids the model from calculating numbers, and the eval harness checks answer numbers against database truth.
- **No charting library,** and a chart palette with one series colour.
- **Data gaps:** there's no period comparison service, and account daily metrics are collected but never read.
- **OpenUI** (thesysdev, MIT): the model writes a UI language rendered by our components. It's TypeScript-first, Gemini output quality is unmeasured, and some packages are pre-1.0 (doc 02).

## Options considered
- **A.** The agent writes OpenUI Lang.
- **B.** Structured agent output plus a presentation adapter.
- **C.** Server-derived typed visuals rendered by our components.
- **D.** A hybrid of C and selective OpenUI. (Doc 03.)

## Decision
Adopt **C**: tools build typed visuals from the same service data they return. The run exposes them as `visuals`, the way it exposes action cards, and the web renders them with our own components. **Do not adopt OpenUI now.** Keep component props JSON-serialisable, so the components can be registered with OpenUI later, and evaluate the hybrid (D) offline once C is live (doc 07, phase 4 gate).

## Why
- **Correct numbers by construction:** the service computes every figure and change, which meets the existing numbers rule and the eval harness.
- **No extra cost or latency:** no added model call or prompt tokens. Visuals are even removed from what the model reads.
- **Smallest change in the right place:** it mirrors action cards, needs no migration, and survives resume and replay.
- **Safer:** the model never authors layout, so prompt injection can't steer the UI, and the closed union admits no unapproved components.
- **The work every option needs** (the period comparison service, the chart components) is the same, so none of it is wasted if we add OpenUI later.

## Rejected
- **A:** puts layout and numbers in model output on an unmeasured model and a Python backend. It adds prompt cost to every turn, and it breaks the text-based citations, fallback and evals.
- **B:** either a second model call (cost, latency, failure) or a template, and a template is C with an extra language.
- **D first:** builds two systems before one is proven.

## Consequences
- **Positive:** consistent, accessible, on-brand visuals; easy unit and eval testing; a kill switch through a flag.
- **Negative:** every new kind of view needs a component and a schema (deliberate). Open-ended layouts ("design me a dashboard") aren't served by chat.
- **Follow-up work:**
  - analytics services for account metrics and trends (doc 07, phase 0);
  - labelled SVG chart components;
  - new ref kinds (`contact`, `account`).

## Outstanding decisions (owner)
1. **Approve option C and the phase 0 → 1 scope** (doc 10, VIS-01 to VIS-06).
2. **Chart colours:** keep one series colour (current = brand, previous = neutral), or approve a second categorical hue (a change to C-075). Recommendation: keep one for v1.
3. **Charting:** keep hand-built SVG (consistent with today), or add a library. Recommendation: hand-built for the 4 to 5 chart types in scope. Reconsider only if interactive charts (zoom, brush) are needed.
4. **Where visuals appear:** Ask panel and Ask page only, or also in proactive standing runs (R2). Recommendation: Ask only.
5. **Language of labels** for Hindi and Hinglish answers: English for v1, or localise. Recommendation: English for v1.
6. **The OpenUI spike** (VIS-14): approve it as an offline evaluation after phase 1, or drop it.
