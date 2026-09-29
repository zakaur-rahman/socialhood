"""Scheduling tools (FR-AGT-02, FR-AGT-03, FR-AGT-05, TA.4; agent-architecture.html §5, §19).

R1:
- list_scheduled_messages(range) / list_scheduled_posts(range): read; services/scheduled and
  publishing (P7), in the workspace's time zone. Scheduled posts are for owners and admins, as
  on the Schedule page (``min_role`` admin).
- prepare_scheduled_message(contact, text, when): draft; resolves the contact, the time
  (agent/timeparse.py) and the reply window, and returns a schedule_message action card: the
  conversation's schedule popover limited to the window. A time outside the window is not
  moved silently: the card has no time and its note gives the latest possible one ("Priya's
  window closes tomorrow at 8:12 AM").

R2: schedule_message / cancel_scheduled_message (low, schedule_messages) through
services/scheduled; schedule_post / reschedule_post / cancel_scheduled_post (high,
schedule_posts) through publishing, which checks the publishing limit and formats.
"""

from __future__ import annotations
