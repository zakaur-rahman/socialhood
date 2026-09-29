"""Ask Social Hood, the agent (TR-AGT-01; agent-architecture.html §2-§4): an orchestration layer
over the services Social Hood already has, beside ai/ (model plumbing), not inside it.

- orchestrator.py: the run's state machine (plan → steps → verify → report), persisting every step
- planner.py: the Pydantic AI loop on Gemini (answer loop in R1, plan first for writes in R2)
- plan.py: Plan, Step, Condition and Ref; condition evaluation by code (R2)
- executor.py: runs one step: tool router, retries, persistence, receipts
- gateway.py: R2, risk tier, role, permissions, mode and limits → execute, approval or refuse
- verify.py: R2, read-back verifiers per write tool
- context.py: memory: workspace facts, brand voice, the thread's earlier exchanges
- timeparse.py: deterministic dates, times and ranges in the workspace's time zone
- registry.py: tool metadata (name, models, risk tier, capability, release) and the registry
- tools/: thin typed adapters over existing services, one module per area

The model never touches SQL, tokens or platform APIs: it chooses tools and fills their typed
arguments; the application validates, authorises, executes and verifies. Tools call services,
which call repositories (tenancy); they never run model-written SQL and never call platform APIs
directly. Run state, approvals, permissions, credits and audit live in our tables (models/agent.py),
Pydantic AI only drives the loop between the model and its tools.
"""
