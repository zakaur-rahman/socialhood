"""GET/POST /webhooks/whatsapp (T3.12; TR-WH-01...04): verification challenge; signed deliveries
split into events and stored once, as for Instagram. T3.12 implements it."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", include_in_schema=False)
