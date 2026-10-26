"""C-135: a name a member saved is never replaced by the platform's profile name."""

from __future__ import annotations

import pytest

from socialhood.models.inbox import Contact
from socialhood.services import contact_names


def contact(name: str | None, source: str = "platform", platform: str | None = None) -> Contact:
    return Contact(display_name=name, name_source=source, platform_name=platform)


def test_a_platform_name_fills_and_updates_a_platform_named_contact() -> None:
    c = contact(None)
    assert contact_names.apply_platform_name(c, "Asha R.") is True
    assert (c.display_name, c.platform_name, c.name_source) == ("Asha R.", "Asha R.", "platform")
    assert contact_names.apply_platform_name(c, "Asha Rao") is True
    assert (c.display_name, c.platform_name) == ("Asha Rao", "Asha Rao")
    assert contact_names.apply_platform_name(c, "Asha Rao") is False  # nothing changed


def test_a_team_name_is_kept_but_the_platform_name_is_recorded() -> None:
    c = contact("Asha (wholesale)", "team", "Asha R.")
    assert contact_names.apply_platform_name(c, "Asha Rao") is False
    assert (c.display_name, c.platform_name, c.name_source) == (
        "Asha (wholesale)",
        "Asha Rao",
        "team",
    )


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_an_empty_name_never_overwrites(empty: str | None) -> None:
    c = contact("Asha R.", "platform", "Asha R.")
    assert contact_names.apply_platform_name(c, empty) is False
    assert (c.display_name, c.platform_name) == ("Asha R.", "Asha R.")


def test_a_member_name_sets_team_and_going_back_copies_the_platform_name() -> None:
    c = contact("Asha R.", "platform", "Asha R.")
    contact_names.set_team_name(c, "  Asha (wholesale) ")
    assert (c.display_name, c.name_source) == ("Asha (wholesale)", "team")
    contact_names.use_platform_name(c)
    assert (c.display_name, c.name_source) == ("Asha R.", "platform")


def test_going_back_without_a_platform_name_keeps_the_saved_one() -> None:
    c = contact("Asha", "team", None)
    contact_names.use_platform_name(c)
    assert (c.display_name, c.name_source) == ("Asha", "platform")
