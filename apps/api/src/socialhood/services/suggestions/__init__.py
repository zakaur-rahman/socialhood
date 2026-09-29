"""Suggested replies and auto replies (T5.4, T5.6, T5.8; TR-AI-06, TR-AI-07; FR-SUG-02…05).

- ``drafting``: one reply drafted from the conversation and knowledge (the suggest prompt),
  shared by inbox suggestions and automations' AI replies;
- ``service``: the suggest_reply job, regenerate, dismiss, and what sending, new messages and
  the conversation detail do with suggestions;
- ``auto``: decide_auto_reply, the policy's decision and what follows it;
- ``knowledge_port``: the retrieval and gap functions owned by T5.3 (an adapter until merge).
"""
