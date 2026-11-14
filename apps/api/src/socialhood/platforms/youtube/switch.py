"""The YouTube feature switch (C-195): YOUTUBE_WORKSPACES is "" (off everywhere), "*" (on for every
workspace) or a comma list of workspace slugs or ids."""

from __future__ import annotations

import uuid
from typing import Literal

from socialhood.settings import Settings

FeatureName = Literal["youtube"]


def youtube_enabled(settings: Settings, workspace_id: uuid.UUID | str, slug: str) -> bool:
    allowed = {item.strip() for item in settings.youtube_workspaces.split(",") if item.strip()}
    return "*" in allowed or slug in allowed or str(workspace_id) in allowed


def features_for(settings: Settings, workspace_id: uuid.UUID | str, slug: str) -> list[FeatureName]:
    """What WorkspaceOut and WorkspaceSummary list in ``features``."""
    return ["youtube"] if youtube_enabled(settings, workspace_id, slug) else []
