"""Read-back verifiers (R2; TR-AGT-06; agent-architecture.html §4 Verifier, §15).

Each write tool has a verifier that reads its effect back, and the platform receipt where one
exists (send results, echoes, webhooks): a scheduled message exists with the returned id and
time; an automation exists with the requested trigger and status; a comment reply has a platform
id. The outcome is stored on the step as ``verification`` ({verified, checked, external_ids};
schemas/agent.StepVerification). Only a verified write is reported as done; any other is "not
confirmed" and makes the run ``partial``. A write step found ``running`` after a crash is checked
here before any retry, so it never runs twice (TR-AGT-07).

No R1 tool writes, so nothing here runs in R1.
"""

from __future__ import annotations
