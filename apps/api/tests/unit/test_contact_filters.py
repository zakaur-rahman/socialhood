"""GR-17: the contacts filter as a body (saved segments, bulk tagging), its parsing and limits."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from socialhood.schemas.contacts import BulkTagsUpdate, ContactFilterSpec, SegmentCreate
from socialhood.services import contacts
from socialhood.services.contact_segments import stored
from socialhood.services.contact_timeline import consent_title


def test_a_field_match_is_a_value_or_any_value() -> None:
    assert contacts.parse_field_match("city:pune") == ("city", "pune")
    assert contacts.parse_field_match("city:*") == ("city", None)
    assert contacts.parse_field_match("note:a:b") == ("note", "a:b")  # only the first colon splits


@pytest.mark.parametrize("bad", ["City:pune", "city", "city:", "1city:x", "x" * 41 + ":y", ":x"])
def test_a_field_match_has_a_lower_case_key_and_a_value(bad: str) -> None:
    with pytest.raises(ValidationError):
        ContactFilterSpec(fields=[bad])


def test_the_spec_keeps_the_lists_limits() -> None:
    with pytest.raises(ValidationError):
        ContactFilterSpec(tag_ids=[uuid.uuid4() for _ in range(11)])
    with pytest.raises(ValidationError):
        ContactFilterSpec(fields=[f"f{i}:x" for i in range(6)])
    with pytest.raises(ValidationError):
        ContactFilterSpec(q="x" * 101)
    with pytest.raises(ValidationError):
        ContactFilterSpec(min_lead_score=101)
    with pytest.raises(ValidationError):
        ContactFilterSpec(platform="tiktok")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ContactFilterSpec(unknown=1)  # type: ignore[call-arg]


def test_an_activity_range_must_run_forward() -> None:
    early = datetime(2026, 1, 1, tzinfo=UTC)
    late = datetime(2026, 2, 1, tzinfo=UTC)
    assert ContactFilterSpec(active_after=early, active_before=late).active_after == early
    with pytest.raises(ValidationError):
        ContactFilterSpec(active_after=late, active_before=early)
    with pytest.raises(ValidationError):
        ContactFilterSpec(active_after=early, active_before=early)


def test_moving_ranges_are_whole_days_within_ten_years() -> None:
    assert ContactFilterSpec(active_within_days=1, inactive_for_days=3650).inactive_for_days == 3650
    for bad in (0, -1, 3651):
        with pytest.raises(ValidationError):
            ContactFilterSpec(active_within_days=bad)
        with pytest.raises(ValidationError):
            ContactFilterSpec(inactive_for_days=bad)


def test_a_moving_range_is_a_bound_on_activity() -> None:
    sql = str(
        contacts._filtered(
            contacts.ContactFilter(active_within_days=7, inactive_for_days=30)
        ).compile(dialect=postgresql.dialect())
    )
    assert sql.count("greatest(") >= 2


def test_a_spec_becomes_the_services_filter() -> None:
    tag = uuid.uuid4()
    account = uuid.uuid4()
    spec = ContactFilterSpec(
        q="priya",
        tag_ids=[tag],
        platform="whatsapp",
        account_id=account,
        has_email=True,
        marketing_consent="whatsapp",
        min_lead_score=40,
        active_within_days=7,
        inactive_for_days=30,
        fields=["city:Pune", "size:*"],
    )
    filt = contacts.filter_from_spec(spec)
    assert filt == contacts.ContactFilter(
        q="priya",
        tag_ids=(tag,),
        platform="whatsapp",
        account_id=account,
        has_email=True,
        marketing_consent="whatsapp",
        min_lead_score=40,
        active_within_days=7,
        inactive_for_days=30,
        fields=(("city", "Pune"), ("size", None)),
    )
    assert contacts.filter_from_spec(ContactFilterSpec()) == contacts.ContactFilter()


def test_a_saved_filter_holds_only_what_is_set_and_reads_back() -> None:
    tag = uuid.uuid4()
    spec = ContactFilterSpec(tag_ids=[tag], has_email=True, fields=["city:*"])
    saved = stored(spec)
    assert saved == {"tag_ids": [str(tag)], "has_email": True, "fields": ["city:*"]}
    assert ContactFilterSpec.model_validate(saved) == spec
    assert stored(ContactFilterSpec()) == {}
    assert ContactFilterSpec.model_validate({}) == ContactFilterSpec()


def test_a_bulk_tag_names_contacts_or_a_filter_not_both_or_neither() -> None:
    contact = uuid.uuid4()
    tag = uuid.uuid4()
    assert BulkTagsUpdate(contact_ids=[contact], add=[tag]).filter is None
    assert BulkTagsUpdate(filter=ContactFilterSpec(has_email=True), add=[tag]).contact_ids is None
    with pytest.raises(ValidationError):
        BulkTagsUpdate(add=[tag])
    with pytest.raises(ValidationError):
        BulkTagsUpdate(contact_ids=[contact], filter=ContactFilterSpec(), add=[tag])
    with pytest.raises(ValidationError):
        BulkTagsUpdate(contact_ids=[], add=[tag])
    with pytest.raises(ValidationError):
        BulkTagsUpdate(contact_ids=[uuid.uuid4() for _ in range(501)], add=[tag])


def test_a_segment_needs_a_name_of_up_to_60_characters() -> None:
    assert SegmentCreate(name=" Leads ", filter=ContactFilterSpec()).name == "Leads"
    for name in ("", "   ", "x" * 61):
        with pytest.raises(ValidationError):
            SegmentCreate(name=name, filter=ContactFilterSpec())


def test_the_query_asks_for_every_tag_and_has_email() -> None:
    """The done-when filter: tag = lead-magnet and has an email."""
    tag = uuid.uuid4()
    sql = str(
        contacts._filtered(contacts.ContactFilter(tag_ids=(tag,), has_email=True)).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "contact_tags" in sql
    assert "contacts.email IS NOT NULL" in sql


def test_consent_in_the_timeline_reads_in_plain_words() -> None:
    assert consent_title("whatsapp", "granted") == "Agreed to marketing on WhatsApp"
    assert consent_title("instagram", "revoked") == "Withdrew marketing consent on Instagram"
