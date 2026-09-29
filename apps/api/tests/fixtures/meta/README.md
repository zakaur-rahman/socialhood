# Meta fixtures

Synthetic payloads in the shapes Meta documents for Instagram API with Instagram Login. Ids and
tokens are made up. T0.9 replaces each file with a recorded, anonymised response from a real test
account (docs/verification.md); tests that use a file must keep passing when it is replaced.

- `webhook_message_*.json`, `webhook_story_*.json`, `webhook_share*.json`, `webhook_echo.json`,
  `webhook_reaction.json`, `webhook_unreact.json`, `webhook_seen.json`, `webhook_postback.json`:
  one delivery per payload type the parser handles (T3.2), all from customer `990000000000001`
  to account `17841400000000001`. `webhook_message_deleted.json` uses `is_deleted`, which Meta
  documents for unsent messages but no real payload has shown yet.
  `webhook_message_quick_reply.json` is a tapped quick reply (`message.quick_reply.payload`,
  T4.8) in the shape Meta documents; no real tap has been recorded yet.
- `webhook_comment_*.json`: both comment shapes (the `changes[]` one is confirmed by a real
  delivery, T0.9 item 2).
- `media_list.json`: `GET /me/media` for sync_media; `conversations_list.json` and
  `conversation_messages.json`: the Conversations API for backfill (T3.14, T0.9 item 7).
