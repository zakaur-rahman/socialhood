"""WhatsApp jobs (T3.12): none of its own.

Inbound media is copied by ingest_media through the adapter's download_media (media id -> URL
valid for 5 minutes -> bytes), like every platform's; templates are read on demand with a short
cache (services/whatsapp_templates.py); the WABA webhook subscription is renewed by
reconcile_subscriptions with the other accounts.
"""

from __future__ import annotations
