"""The workspace folder purge against Cloudinary's Admin API (T9.6): delete resources by prefix
(DELETE /resources/{type}/upload?prefix=, up to 1000 per call, ``partial`` and ``next_cursor``
while more remain) for each resource type, then DELETE /folders/{path}
(https://cloudinary.com/documentation/admin_api#delete_resources and #delete_folder). respx stands
in for api.cloudinary.com; no test reaches it."""

from __future__ import annotations

import base64
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from pydantic import SecretStr

from socialhood.media.cloudinary import API, CloudinaryError
from socialhood.media.purge import CloudinaryPurger
from socialhood.settings import Settings

CLOUD = "demo-cloud"
KEY = "123456789012345"
SECRET = "fake-cloudinary-secret-for-tests"
WID = uuid.UUID("5f0c3c1e-2d7a-4b43-9d35-9d7f0b0c2a11")


@pytest.fixture
def settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "cloudinary_cloud_name": CLOUD,
            "cloudinary_api_key": KEY,
            "cloudinary_api_secret": SecretStr(SECRET),
        }
    )


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def resources(resource_type: str) -> str:
    return f"{API}/{CLOUD}/resources/{resource_type}/upload"


FOLDER = f"{API}/{CLOUD}/folders/ws/{WID}"


async def test_every_type_is_deleted_by_prefix_then_the_folder(
    settings: Settings, http: httpx.AsyncClient
) -> None:
    with respx.mock(assert_all_called=True) as router:
        image = router.delete(resources("image")).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "deleted": {f"ws/{WID}/post/a": "deleted"},
                        "partial": True,
                        "next_cursor": "c1",
                    },
                ),
                httpx.Response(
                    200, json={"deleted": {f"ws/{WID}/post/b": "deleted"}, "partial": False}
                ),
            ]
        )
        video = router.delete(resources("video")).respond(200, json={"deleted": {}})
        raw = router.delete(resources("raw")).respond(200, json={"deleted": {}})
        folder = router.delete(FOLDER).respond(200, json={"deleted": [f"ws/{WID}"]})

        await CloudinaryPurger(http, settings).delete_workspace_folder(WID)

    first, second = image.calls
    assert first.request.url.params["prefix"] == f"ws/{WID}/"
    assert "next_cursor" not in first.request.url.params
    assert second.request.url.params["next_cursor"] == "c1"
    basic = "Basic " + base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
    for call in (*image.calls, *video.calls, *raw.calls, *folder.calls):
        assert call.request.headers["authorization"] == basic


async def test_a_folder_cloudinary_doesnt_know_is_already_gone(
    settings: Settings, http: httpx.AsyncClient
) -> None:
    with respx.mock() as router:
        for resource_type in ("image", "video", "raw"):
            router.delete(resources(resource_type)).respond(200, json={"deleted": {}})
        router.delete(FOLDER).respond(404, json={"error": {"message": "Can't find folder"}})
        await CloudinaryPurger(http, settings).delete_workspace_folder(WID)


@pytest.mark.parametrize(
    ("resources_status", "folder_status"), [(500, 200), (420, 200), (200, 400)]
)
async def test_a_failure_raises_so_the_purge_tries_again(
    settings: Settings, http: httpx.AsyncClient, resources_status: int, folder_status: int
) -> None:
    with respx.mock(assert_all_called=False) as router:  # the first failure stops the purge
        for resource_type in ("image", "video", "raw"):
            router.delete(resources(resource_type)).respond(resources_status, json={})
        router.delete(FOLDER).respond(folder_status, json={})
        with pytest.raises(CloudinaryError):
            await CloudinaryPurger(http, settings).delete_workspace_folder(WID)


async def test_without_credentials_nothing_was_uploaded_so_nothing_is_called(
    api_settings: Settings, http: httpx.AsyncClient
) -> None:
    unconfigured = api_settings.model_copy(update={"cloudinary_cloud_name": None})
    with respx.mock(assert_all_mocked=True):
        await CloudinaryPurger(http, unconfigured).delete_workspace_folder(WID)
