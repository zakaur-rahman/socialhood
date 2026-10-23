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
- GR-06 and GR-07: `webhook_story_reply.json` carries `reply_to.story` with its `url` and `id`,
  `webhook_story_like.json` is the same with only the heart sticker (a story like), and
  `webhook_story_mention.json` is a `story_mention` attachment whose `payload.url` is the story's
  CDN address, which expires with the story. All in the shapes Meta documents, none recorded yet;
  whether the story `id` equals the id `GET /me/stories` lists is unverified (T0.9).
  `stories_list.json` is `GET /me/stories` (the account's live stories).
- GR-01, in the shapes of Meta's Instagram webhook examples (2026), none recorded yet:
  `webhook_referral_link.json` (`messaging_referral`: an ig.me link with `ref` opened),
  `webhook_message_from_ad.json` (a message whose `referral` is an ad: `source: "ADS"`, `ad_id`,
  `ads_context_data`), `webhook_optin.json` (`messaging_optins`) and `webhook_live_comment.json`
  (`live_comments`, whose id is `comment_id`). `webhook_postback.json` doubles as an ice breaker
  tap (its `payload`). `whatsapp_webhook_from_ad.json` is a Click to WhatsApp ad message
  (`referral` with `source_type: ad`, `source_id`, `headline`, `ctwa_clid`; Meta's messages
  webhook reference).
- `webhook_comment_*.json`: both comment shapes (the `changes[]` one is confirmed by a real
  delivery, T0.9 item 2).
- `media_list.json`: `GET /me/media` for sync_media; `conversations_list.json` and
  `conversation_messages.json`: the Conversations API for backfill (T3.14, T0.9 item 7).
- Metric snapshots (T6.5, FR-ANL-01), in the shapes of Meta's Media Insights and Account Insights
  references (checked 2026-09-29), none recorded yet: `media_counts.json` (`GET /{media_id}?
  fields=like_count,comments_count`), `media_insights_feed.json` and `media_insights_reel.json`
  (`GET /{media_id}/insights`, lifetime `values[]`), `me_followers.json`,
  `user_insights_day.json` (`GET /{ig_user_id}/insights?period=day&metric_type=total_value`),
  `user_insights_follows.json` (`follows_and_unfollows` with the `follow_type` breakdown), and
  the refusals `error_100_incompatible_metric.json`, `error_100_33_missing_media.json`,
  `error_10_insights_permission.json`.
- `media_comments_page1.json` and `media_comments_page2.json`: `GET /{media_id}/comments` with
  replies expanded, for the comment backfill (T6.1): a question with the account's own reply and a
  customer's, hidden spam, a comment without `from` (left out), and the `after` cursor to the last
  page.
- `error_100_33_not_found.json`: the error Meta documents for a write on an object that no longer
  exists, such as a deleted comment (T6.3); not yet seen from a real account.
- Content publishing (T7.2, FR-PUB-05), in the shapes of Meta's Content Publishing guide and the
  IG User Media, IG Container and Content Publishing Limit references (checked 2026-09-29), none
  recorded yet: `publishing_limit.json` (`GET /{ig}/content_publishing_limit?fields=quota_usage,
  config`), `container_created.json` (`POST /{ig}/media`), `container_status_finished.json`,
  `container_status_in_progress.json` and `container_status_error.json` (`GET /{container}?
  fields=status_code,status`; the ERROR text with its subcode is a guess at the wording),
  `media_publish.json` (`POST /{ig}/media_publish`), `published_media.json` (the read-back),
  `comment_created.json` (`POST /{media_id}/comments`) and the refusals
  `error_2207042_publishing_limit.json`, `error_2207027_not_ready.json`,
  `error_2207009_aspect_ratio.json` (codes and subcodes from Meta's error-code reference).
