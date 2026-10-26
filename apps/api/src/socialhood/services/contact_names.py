"""Whose name a contact carries (C-135).

``contacts.display_name`` is what the app shows. A platform (Instagram, Facebook, WhatsApp, the
web widget) sends a profile name with every message; a member can also type a name. The rule is
the same on every channel:

- the platform's latest name is always kept in ``platform_name``;
- it becomes ``display_name`` only while ``name_source`` is ``platform``;
- a name a member typed (rename, create, import) sets ``name_source`` to ``team`` and is never
  replaced by a platform name;
- "use the platform name" hands the name back: ``name_source`` is ``platform`` again and the
  saved platform name is copied over (when there is one).

An empty or missing platform name never overwrites anything.
"""

from __future__ import annotations

from socialhood.models.contacts import NameSource
from socialhood.models.inbox import Contact


def clean(name: str | None) -> str | None:
    """A name with its edges trimmed; None for a missing or blank one."""
    stripped = (name or "").strip()
    return stripped or None


def apply_platform_name(contact: Contact, name: str | None) -> bool:
    """Record the name a platform sent. True when the shown name changed."""
    new = clean(name)
    if new is None:
        return False
    contact.platform_name = new
    if contact.name_source == NameSource.TEAM or contact.display_name == new:
        return False
    contact.display_name = new
    return True


def set_team_name(contact: Contact, name: str) -> None:
    """A member typed this name: it stays until they hand the name back to the platform."""
    contact.display_name = name.strip()
    contact.name_source = NameSource.TEAM


def use_platform_name(contact: Contact) -> None:
    """Go back to the platform's name. Without one on record the saved name stays shown until the
    next message brings it."""
    contact.name_source = NameSource.PLATFORM
    if contact.platform_name:
        contact.display_name = contact.platform_name
