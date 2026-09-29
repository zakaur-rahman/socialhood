"""Publishing jobs (T7.3; F-13, FR-PUB-05, FR-PUB-06, FR-PUB-11, FR-AUT-18, TR-JOB-02…05).
Thin tasks: the work belongs in services. Interactive lane (TR-JOB-06). Each task carries the
workspace id, so none needs a cross-workspace lookup after the dispatcher's claim (C-020).

- dispatch_due_posts: periodic, every 30 s (``* * * * * */30``, queueing lock). Claims the pending
  targets of posts whose publish_at has come (post scheduled or publishing), across workspaces
  with FOR UPDATE SKIP LOCKED (allowed in jobs/, TR-TEN-04), at most 200 at a time: target
  ``publishing``, claimed_at = now, attempts + 1; the post becomes ``publishing``
  (scheduled_post.updated). Enqueues publish_target for each under ``pub:{target_id}``. Its own
  task, like dispatch_comment_analysis: dispatch_due is the scheduled-message dispatcher.
- publish_target(target_id, workspace_id): also enqueued by publish now. Reads the publishing
  quota first (none left: target failed with the reason); creates the containers through the
  adapter (children first, in order, for a carousel; images and videos by their delivery URLs)
  and stores child_container_ids and container_id (status ``container_created``); then enqueues
  poll_container(target_id, 1). Transient platform errors retry up to 3 times (FR-PUB-05,
  PlatformRetry); the last attempt or a refusal marks the target failed. Lock ``pub:{target_id}``,
  120 s.
- poll_container(target_id, n, workspace_id): one status read. IN_PROGRESS: re-enqueue itself as
  n + 1 after 60 s for polls 1 to 5, then 5 minutes up to poll 10 (models/publishing.py POLL_*);
  still IN_PROGRESS after poll 10: failed "Instagram took too long to process the video".
  FINISHED: publish the container (a lost answer, delivery_unknown, is resolved through the
  container's status and find_published_media, never by publishing twice), read the post back
  (permalink), then in one transaction: target published; the post's status derived from its
  targets (models/publishing.py); insert the media_items row (published_target_id) and link
  waiting automations (services/automations/posts.link_scheduled_post and link_next_posts);
  enqueue post_first_comment when the post has one. ERROR or EXPIRED: failed with Instagram's
  reason. A post ending failed or partly published notifies the owners and admins (FR-PUB-06).
  Lock ``poll:{target_id}:{n}``, 30 s, 1 try.
- post_first_comment(target_id, workspace_id): the first comment on the published post
  (FR-PUB-11); stores first_comment_platform_id, or first_comment_error after the last of 3
  tries; the post stays published either way. Lock ``firstc:{target_id}``.
- sweep_stuck_posts: periodic, every minute. Targets left ``publishing`` for more than 10 minutes
  go back to pending (failed after the last attempt), and ``container_created`` targets whose poll
  chain was lost get their next poll enqueued (TR-JOB-03).
"""

from __future__ import annotations
