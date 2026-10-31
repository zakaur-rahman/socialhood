"""The Amplychat MCP server (C-165; docs/architecture/mcp/): Claude, ChatGPT and Codex reach a
workspace through /mcp on the API.

- server.py: the SDK server and its mounting at /mcp (stateless Streamable HTTP);
- http.py: authentication in front of the transport, and the protected resource metadata;
- auth.py: credential resolvers (API keys now, OAuth tokens in phase C) → principal.py;
- registry.py: tools and their conventions; calls.py: the gate, limits and audit every call
  goes through; idempotency.py, audit.py, results.py;
- tools/: the tools.
"""
