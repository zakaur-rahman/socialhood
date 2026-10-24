"""GR-27 Google Sheets sync: the pure parts (the row's cells, the sheet link, the reasons) and the
fake Google that every other test stands on."""

from __future__ import annotations

import pytest

from socialhood.google.client import GoogleError
from socialhood.google.fake import FakeGoogle
from socialhood.services import sheets
from socialhood.services.webhooks import delivery

SOURCE = {
    "contact_name": "Priya Nair",
    "username": "priya.n",
    "platform": "Instagram",
    "email": "priya@example.com",
    "phone": "+919876543210",
    "automation": "Free guide",
    "captured_at": "2026-10-24T09:30:00Z",
    "consent": "Yes",
    "fields": {"city": "Kochi", "vip": True, "interests": ["tea", "gifts"], "size": None},
}


def test_a_row_follows_the_column_order() -> None:
    mapping = [
        {"field": "email", "header": "Mail"},
        {"field": "contact_name", "header": "Who"},
        {"field": "field:city", "header": "City"},
    ]
    assert sheets.row_values(mapping, SOURCE) == ["priya@example.com", "Priya Nair", "Kochi"]


def test_custom_field_values_are_plain_text() -> None:
    mapping = [{"field": f"field:{k}", "header": k} for k in ("vip", "interests", "size", "gone")]
    assert sheets.row_values(mapping, SOURCE) == ["Yes", "tea, gifts", "", ""]


def test_a_missing_value_is_an_empty_cell() -> None:
    assert sheets.row_values([{"field": "phone", "header": "P"}], {}) == [""]


def test_every_fixed_field_has_a_default_header() -> None:
    assert [c.field for c in sheets.DEFAULT_COLUMNS] == list(sheets.FIELDS)
    assert {c.header for c in sheets.DEFAULT_COLUMNS} >= {"Name", "Email", "Captured at"}


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        (
            "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0",
            "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        ),
        (
            "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        ),
        (
            "  1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms  ",
            "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        ),
        ("https://example.com/not-a-sheet", None),
        ("short", None),
        ("has spaces in it and more", None),
    ],
)
def test_the_sheet_link_or_id_is_understood(link: str, expected: str | None) -> None:
    assert sheets.sheet_id_of(link) == expected


def test_every_reason_is_plain_words() -> None:
    assert sheets.REASONS[sheets.ACCESS_REMOVED] == (
        "Access was removed: reconnect Google in Settings, under Integrations."
    )
    assert sheets.REASONS[sheets.SHEET_GONE].startswith("Google said the sheet was deleted.")
    for reason in sheets.REASONS.values():
        assert reason.endswith(".")
        assert "please" not in reason.lower()


def test_the_retries_use_the_webhook_backoff() -> None:
    assert delivery.backoff(1) is not None
    assert delivery.backoff(delivery.MAX_ATTEMPTS) is None


def test_only_the_narrow_scope_is_asked_for() -> None:
    from socialhood.google.client import SCOPES

    assert SCOPES == ("https://www.googleapis.com/auth/drive.file", "openid", "email")


# ---------------------------------------------------------------- the fake


async def test_the_fake_signs_in_creates_and_appends() -> None:
    fake = FakeGoogle("https://api.test/cb")
    assert fake.authorize_url("s1").startswith("https://api.test/cb?code=fake-code")
    grant = await fake.exchange_code("fake-code:a@b.test")
    assert grant.email == "a@b.test"
    access = await fake.access_token(grant.refresh_token)
    info = await fake.create_spreadsheet(access, "Leads", ["Name"])
    await fake.append_row(access, info.spreadsheet_id, info.tab, ["Priya"])
    assert await fake.rows(info.spreadsheet_id) == [["Priya"]]
    assert await fake.header(info.spreadsheet_id) == ["Name"]


async def test_the_fake_only_sees_sheets_it_made_or_was_given() -> None:
    fake = FakeGoogle()
    grant = await fake.exchange_code("fake-code:a@b.test")
    access = await fake.access_token(grant.refresh_token)
    with pytest.raises(GoogleError) as unseen:
        await fake.get_spreadsheet(access, "someone-elses-sheet")
    assert unseen.value.kind == "not_found"
    await fake.add_sheet("opened-sheet-1", "Opened")
    assert (await fake.get_spreadsheet(access, "opened-sheet-1")).title == "Opened"


async def test_revoked_access_and_a_deleted_sheet_fail_as_google_does() -> None:
    fake = FakeGoogle()
    grant = await fake.exchange_code("fake-code:a@b.test")
    access = await fake.access_token(grant.refresh_token)
    info = await fake.create_spreadsheet(access, "Leads", [])
    await fake.delete_sheet(info.spreadsheet_id)
    with pytest.raises(GoogleError) as gone:
        await fake.append_row(access, info.spreadsheet_id, info.tab, ["x"])
    assert gone.value.kind == "not_found"
    await fake.revoke_access(grant.refresh_token)
    with pytest.raises(GoogleError) as revoked:
        await fake.access_token(grant.refresh_token)
    assert revoked.value.kind == "auth"


async def test_a_queued_failure_is_raised_once() -> None:
    fake = FakeGoogle()
    fake.fail_next(GoogleError("unavailable"))
    with pytest.raises(GoogleError):
        await fake.exchange_code("fake-code:a@b.test")
    assert (await fake.exchange_code("fake-code:a@b.test")).email == "a@b.test"
