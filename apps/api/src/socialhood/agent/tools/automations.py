"""Automation tools (FR-AGT-02, FR-AGT-03, TA.4; agent-architecture.html §5). Owners and admins,
as in the UI (``min_role`` admin).

R1:
- list_automations / get_automation / get_automation_stats: read; services/automations
  (definitions, runs and per-automation results, FR-AUT-17).
- test_automation(id, kind, text): read; the editor's test box (which automation would answer,
  and what), which sends nothing.
- prepare_automation(description): draft; a template and definition for the request, returned as
  an automation_draft action card that opens the editor unsaved and pre-filled (F-11); the
  member saves and activates it there.

R2: create_automation_draft (low, create_automations), activate_automation (high) and
pause_automation (low) (create_automations), delete_automation (destructive,
delete_automations); services/automations/definitions.
"""

from __future__ import annotations
