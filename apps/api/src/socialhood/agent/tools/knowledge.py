"""Knowledge tools (FR-AGT-02, TA.4; agent-architecture.html §5). Owners and admins, as in the
UI (``min_role`` admin); the brand voice reaches every run through the system prompt instead.

R1 (all read):
- search_knowledge(q): retrieval over the knowledge base (TR-AI-08); the matching sources as
  knowledge_source refs.
- answer_from_knowledge(question): the Knowledge page's test box (T5.3, charges knowledge_test);
  stores and sends nothing.
- list_knowledge_gaps(): questions the AI couldn't answer in the last 30 days (T5.10).

No writes.
"""

from __future__ import annotations
