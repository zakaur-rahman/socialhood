"""Facebook Page connect shapes (GR-29): the Pages a person can connect, and the ones they pick."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

from socialhood.schemas.common import RequestModel, ResponseModel

PageId = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class FacebookPagesRequest(RequestModel):
    """The nonce the OAuth callback put in the Connections page's URL (?facebook=…)."""

    nonce: str = Field(min_length=1, max_length=128)


class FacebookConnectPages(RequestModel):
    """The Pages to connect, picked from the list the same nonce returned."""

    nonce: str = Field(min_length=1, max_length=128)
    page_ids: list[PageId] = Field(min_length=1, max_length=25)


class FacebookPageOption(ResponseModel):
    id: str
    name: str | None = None
    username: str | None = None
    picture_url: str | None = None
    # Already connected in this workspace (live): picking it reconnects it.
    connected: bool = False
    # False with ``problem`` set: the person can't answer messages for this Page.
    can_connect: bool = True
    problem: str | None = None


class FacebookPageList(ResponseModel):
    items: list[FacebookPageOption]
