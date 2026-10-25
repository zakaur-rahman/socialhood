"""WhatsApp broadcasts (GR-23).

- ``stop``: the words that withdraw marketing consent (pure).
- ``throttle``: how many messages may go out now, from the number's daily limit (pure).
- ``rates``: Meta's rate card as data, and the cost estimate (pure).
- ``variables``: template variables mapped to contact fields or fixed values (pure).
- ``audience``: who a broadcast reaches and who it skips, from the segment and consent.
- ``service``: create, preview, start, pause, resume, cancel, and the reads for the pages.
- ``dispatch``: one batch of a running broadcast (the job's work).
- ``health``: a number's quality rating and daily limit, and the pause when quality drops.
- ``inbound``: what a customer's message does to broadcasts (STOP, replies).
"""
