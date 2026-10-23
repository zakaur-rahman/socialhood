# Generative UI for Ask Social Hood

An investigation of how the existing agent could answer with charts, KPI cards, tables and safe actions, and whether to use OpenUI for it. **Status:** the owner approved option C (doc 08) on 2026-10-24. It's planned as **GR-38** in `docs/roadmap/IMPLEMENTATION_PLAN.md` (batch 3, first); not started.

| Doc | What's in it |
|---|---|
| [01 Existing system audit](01-existing-system-audit.md) | How the agent works today, traced through the code; what data and UI exist |
| [02 OpenUI research](02-openui-research.md) | What OpenUI is, from official sources; verified, assumed, unresolved |
| [03 Architecture options](03-architecture-options.md) | Four approaches compared; the recommendation and a diagram |
| [04 Generative UI design](04-generative-ui-design.md) | Experience, component catalogue, response selection, example flows |
| [05 Response contract](05-response-contract.md) | Schemas, computation rules, streaming, validation, fallback |
| [06 Security and reliability](06-security-and-reliability.md) | Threat model, rules, tests, safeguards |
| [07 Implementation roadmap](07-implementation-roadmap.md) | Phases, model and cost strategy, evaluation plan, risks |
| [08 Decision record](08-decision-record.md) | The proposed decision and what needs the owner |
| [09 Product opportunities](09-product-opportunities.md) | Ranked ideas beyond basic charts |
| [10 Implementation backlog](10-implementation-backlog.md) | Task list (VIS-01 to VIS-14) |

**In one line:**
- Build typed visuals that our tools derive from service data, rendered with our own components, the same way action cards work today.
- Keep OpenUI out of the critical path, and evaluate it offline later.
