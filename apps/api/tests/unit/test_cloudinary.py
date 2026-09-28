"""TR-MED-01 signing and workspace folders."""

from __future__ import annotations

import uuid

from socialhood.media.cloudinary import in_workspace, sign, workspace_folder


def test_signature_matches_cloudinarys_documented_example() -> None:
    params = {
        "eager": "w_400,h_300,c_pad|w_260,h_200,c_crop",
        "public_id": "sample_image",
        "timestamp": 1315060510,
        "api_key": "ignored",
        "file": "ignored",
    }
    assert sign(params, "abcd") == "bfd09f95f331f558cbd1320e67aa8d488770583e"


def test_assets_must_be_in_the_workspace_folder() -> None:
    wid = uuid.uuid4()
    assert workspace_folder(wid, "message") == f"ws/{wid}/message"
    assert in_workspace(f"ws/{wid}/message/abc", wid)
    assert not in_workspace(f"ws/{uuid.uuid4()}/message/abc", wid)
    assert not in_workspace(f"ws/{wid}", wid)
