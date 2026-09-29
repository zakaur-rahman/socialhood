"""Conversation and customer tools (FR-AGT-02, FR-AGT-03, TA.4; agent-architecture.html §5).

R1:
- search_conversations(q, view, account, range): read; services/conversations (inbox search,
  views, filters). Capped list with how many more.
- get_conversation(id, last_n): read; the conversation with its latest messages, summary
  (FR-AI-03) and latest analysis (intent, sentiment, lead score).
- find_contact(name_or_handle) / get_customer(id): read; contacts and their analyses. Several
  matches are listed for the model to ask which one.
- draft_reply(conversation_id, instructions): draft; the suggestion drafting path (TR-AI-06,
  charges reply_suggestion); returns the text for the member, sends nothing.

R2: send_message(conversation_id, text): high, capability send_replies; sending.queue_outbound.
"""

from __future__ import annotations
