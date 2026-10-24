"""Sequences (GR-24): timed follow-up messages after an entry event.

- ``rules``: what a step may send now, and why it is skipped (pure).
- ``schedule``: when a step is due, and the next time business hours are open (pure).
- ``entry``: the entry and stop events, called from where contacts are captured (GR-14), tagged
  (GR-02), move lead stage (GR-18) and write (ingest, with GR-23's broadcast replies).
- ``service``: create, change, activate, pause, delete and the reads for the pages.
- ``runner``: the sweeper's work, one due enrolment at a time.
"""
