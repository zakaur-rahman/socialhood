"""C-146: links to public pages go to the site, links into the app to the app."""

from __future__ import annotations

import base64
import uuid

from socialhood.notify.outbox import unsubscribe_links
from socialhood.settings import Settings

KEY = base64.urlsafe_b64encode(b"k" * 32).decode()
BASE = {
    "database_url": "postgresql+asyncpg://u:p@db/x",
    "database_url_direct": "postgresql://u:p@db/x",
    "redis_url": "redis://kv:6379/0",
    "token_encryption_keys": KEY,
}


def make(**values: object) -> Settings:
    return Settings(_env_file=None, **{**BASE, **values})  # type: ignore[arg-type]


def test_the_unsubscribe_page_is_on_the_site() -> None:
    settings = make(
        web_base_url="https://dashboard.amplychat.com", site_base_url="https://amplychat.com"
    )
    page, _ = unsubscribe_links(settings, uuid.uuid4(), uuid.uuid4())
    assert page.startswith("https://amplychat.com/unsubscribe?token=")


def test_one_origin_keeps_the_unsubscribe_page_on_the_web_url() -> None:
    settings = make(web_base_url="http://localhost:3000")
    page, _ = unsubscribe_links(settings, uuid.uuid4(), uuid.uuid4())
    assert page.startswith("http://localhost:3000/unsubscribe?token=")
