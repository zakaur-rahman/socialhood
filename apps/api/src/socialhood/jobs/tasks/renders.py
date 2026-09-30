"""Render jobs (P7b, TB.2; FR-PUB-21, TR-MED-05, TR-JOB-02…06; docs/editor-spike.md). Thin tasks:
the work is in services/media_renders.py. Each task carries the workspace id; only the sweeper
looks across workspaces (allowed in jobs/, TR-TEN-04). Photos never come here: they render on the
fly and are ``ready`` when created.

- start_render(render_id, workspace_id): interactive lane, queueing lock ``render:{render_id}``,
  timeout 60 s, RENDER_START_ATTEMPTS tries with backoff on CloudinaryError (timeouts, 429, 5xx).
  Enqueued after a pending video render commits. Sends Cloudinary's Explicit API call for the
  source (``POST /video/explicit`` with ``type=upload``, ``eager={transformation}/mp4``,
  ``eager_async=true`` and, when API_BASE_URL is set, an ``eager_notification_url`` pointing at
  the API's /webhooks/cloudinary), stores the batch_id and the derived secure_url it
  answers with, sets ``rendering`` and started_at, publishes media_render.updated, and enqueues
  poll_render(n=1) after RENDER_POLL_DELAY. A render no longer pending is left alone (a
  duplicate job is harmless); a 4xx that isn't a rate limit fails the render with the reason.
- poll_render(render_id, workspace_id, n): interactive lane, lock ``renderpoll:{render_id}:{n}``,
  timeout 30 s, 1 try; re-enqueues itself every RENDER_POLL_DELAY up to RENDER_POLL_MAX. Reads
  the source's derived files (Admin API ``GET resources/video/upload/{public_id}`` with
  ``max_results=500``; ``derived`` lists ``transformation`` URL-decoded, ``format``, ``bytes``,
  ``secure_url``) and finishes the render when its transformation is there. The fallback for a
  lost or unconfigured notification; a render the webhook already finished is left alone. Never
  HEAD the derived URL to poll: on a small video that renders it again on the fly (spike).
- sweep_stuck_renders: periodic, every 5 minutes (bulk lane, singleton). Pending renders older
  than RENDER_STUCK_AFTER with no start_render waiting are enqueued again; renders unfinished
  after RENDER_TIMEOUT are failed ("Rendering took too long. Try again."). models/media.py has
  the timings.
"""

from __future__ import annotations
