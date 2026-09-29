"""The knowledge base (T5.3, T5.10; TR-AI-08, TR-AI-12, FR-KB-01…06).

- ``sources``: create, edit, list and delete sources; the knowledge_characters limit.
- ``ingest``: the ingest_knowledge_source job's work (extract, split, embed, replace chunks).
- ``chunking`` and ``extract``: pure text functions.
- ``retrieval.retrieve``: the nearest chunks for a question (used by suggestions and the test).
- ``answer``: the KNOWLEDGE block for the suggest prompt, and the Knowledge page's test box.
- ``gaps``: questions the AI couldn't answer (``record_gap``) and their list.
"""
