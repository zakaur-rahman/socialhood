"""The editor's spec and builder (P7b; TR-MED-04): every golden case in
packages/editor-fixtures/transform-cases.json (the web's vitest suite runs the same file), the
file is what the generator writes, and EditSpec's limits and problems()."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from socialhood.media.editor.spec import (
    TEXT_MAX_CHARS,
    EditSpec,
    constants,
    is_empty,
    problems,
    spec_hash,
)
from socialhood.media.editor.transform import (
    AssetMeta,
    Built,
    TransformError,
    build,
    cover,
    encode_text,
    fmt,
    rhu,
    still,
)
from tests.support.editor import FIXTURES, lenient_spec, load_fixtures

FIXTURE_DATA = load_fixtures()
CASES = FIXTURE_DATA["cases"]
LOGO_ID = "0b8f6f5e-2f1d-4d57-a0f4-7c55b3c1d9e2"


def _as_dict(built: Built) -> dict[str, Any]:
    out = {
        "kind": built.kind,
        "transformation": built.transformation,
        "format": built.format,
        "url": built.url,
        "width": built.width,
        "height": built.height,
    }
    if built.duration_s is not None:
        out["duration_s"] = built.duration_s
    return out


# ---------------------------------------------------------------- golden cases


def test_there_are_enough_cases_covering_photos_video_carousels_and_text() -> None:
    names = [c["name"] for c in CASES]
    assert len(CASES) >= 40
    assert sum(n.startswith("image:") for n in names) >= 15
    assert sum(n.startswith("video:") for n in names) >= 15
    assert sum(n.startswith("carousel") for n in names) >= 3
    assert any("Hindi" in n for n in names)
    assert any("emoji" in n for n in names)
    assert any("comma, slash and percent" in n for n in names)


def test_the_file_is_what_the_generator_writes() -> None:
    path = Path(__file__).resolve().parents[2] / "scripts" / "editor_fixtures.py"
    spec = importlib.util.spec_from_file_location("editor_fixtures", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = json.dumps(module.render(), indent=2, ensure_ascii=False) + "\n"
    assert FIXTURES.read_text(encoding="utf-8") == expected, "run scripts/editor_fixtures.py"


def test_the_constants_in_the_file_are_the_specs() -> None:
    assert FIXTURE_DATA["constants"] == json.loads(json.dumps(constants()))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_case(case: dict[str, Any]) -> None:
    asset = AssetMeta(**case["asset"])
    logo = case.get("logo_public_id")
    try:
        EditSpec.model_validate(case["spec"])
        valid = True
    except ValidationError:
        valid = False
    assert valid == case["valid"]
    spec = lenient_spec(case["spec"])

    assert _as_dict(build(asset, spec, logo_public_id=logo)) == case["expect"]["build"]
    for expected in case["expect"]["stills"]:
        made = still(
            asset,
            spec,
            at_s=expected["at_s"],
            max_width=expected["max_width"],
            logo_public_id=logo,
        )
        wanted = {k: v for k, v in expected.items() if k not in ("at_s", "max_width")}
        assert _as_dict(made) == wanted
    made_cover = cover(asset, spec, logo_public_id=logo)
    assert (None if made_cover is None else _as_dict(made_cover)) == case["expect"]["cover"]


# ---------------------------------------------------------------- numbers and text


def test_rounding_and_seconds_match_javascript() -> None:
    assert [rhu(v) for v in (0.5, 1.5, 2.5, -0.5, 607.5)] == [1, 2, 3, 0, 608]
    assert [fmt(v) for v in (0, 1, 1.5, 2.25, 3.333, 0.005, 12.1)] == [
        "0",
        "1",
        "1.5",
        "2.25",
        "3.33",
        "0.01",
        "12.1",
    ]


def test_text_is_encoded_for_cloudinary() -> None:
    assert encode_text("a, b/c 50%") == "a%252C%20b%252Fc%2050%2525"
    assert encode_text("Café 🔥") == "Caf%C3%A9%20"
    assert encode_text("line\nnext") == "line%0Anext"
    assert encode_text("a_b-c.d~e") == "a_b-c.d~e"


def test_media_without_a_size_or_a_logo_without_its_file_cant_be_built() -> None:
    photo = AssetMeta("c", "ws/x/post/a", "image", 0, 0)
    with pytest.raises(TransformError):
        build(photo, EditSpec())
    sized = AssetMeta("c", "ws/x/post/a", "image", 100, 100)
    with pytest.raises(TransformError):
        build(sized, EditSpec.model_validate({"logo": {"asset_id": LOGO_ID}}))


# ---------------------------------------------------------------- the spec


@pytest.mark.parametrize(
    ("raw", "where"),
    [
        ({"texts": [{"text": f"t{i}"} for i in range(6)]}, "texts"),
        ({"texts": [{"text": "x" * (TEXT_MAX_CHARS + 1)}]}, "texts.0.text"),
        ({"texts": [{"text": "   "}]}, "texts.0.text"),
        ({"texts": [{"text": "hot \U0001f525"}]}, "texts.0.text"),
        ({"texts": [{"text": "tab\there"}]}, "texts.0.text"),
        ({"texts": [{"text": "1\n2\n3\n4\n5\n6"}]}, "texts.0.text"),
        ({"texts": [{"text": "a", "start_s": 3, "end_s": 2}]}, "texts.0"),
        ({"texts": [{"text": "a", "color": "red"}]}, "texts.0.color"),
        ({"texts": [{"text": "a", "size": 0.5}]}, "texts.0.size"),
        ({"texts": [{"text": "a", "font": "comic"}]}, "texts.0.font"),
        ({"trim": {"start_s": 2, "end_s": 2.5}}, "trim"),
        ({"speed": 3}, "speed"),
        ({"crop": {"aspect": "4:5", "zoom": 5}}, "crop.zoom"),
        ({"crop": {"aspect": "3:2"}}, "crop.aspect"),
        ({"adjust": {"brightness": -100}}, "adjust.brightness"),
        ({"adjust": {"vignette": -1}}, "adjust.vignette"),
        ({"logo": {"asset_id": "not-a-uuid"}}, "logo.asset_id"),
        ({"logo": {"asset_id": LOGO_ID, "opacity": 5}}, "logo.opacity"),
        ({"fade_in_s": 3.5}, "fade_in_s"),
        ({"rotate": 45}, "rotate"),
        ({"look": "daenerys"}, "look"),
        ({"v": 2}, "v"),
        ({"blur": 10}, "blur"),
    ],
)
def test_the_spec_refuses_what_cant_be_drawn_or_is_out_of_range(
    raw: dict[str, Any], where: str
) -> None:
    with pytest.raises(ValidationError) as error:
        EditSpec.model_validate(raw)
    locations = {".".join(str(p) for p in e["loc"]) for e in error.value.errors()}
    assert any(loc == where or loc.startswith(where + ".") for loc in locations), locations


def test_the_largest_valid_spec_is_accepted() -> None:
    spec = EditSpec.model_validate(
        {
            "texts": [
                {"text": "x" * TEXT_MAX_CHARS},
                {"text": "नमस्ते ❤ ★\nline two", "start_s": 0, "end_s": 0.5},
                {"text": "3"},
                {"text": "4"},
                {"text": "5"},
            ],
            "speed": 0.5,
            "adjust": {"brightness": 100, "sharpen": 400, "gamma": -50},
            "crop": {"aspect": "9:16", "zoom": 4, "x": 0, "y": 1},
            "logo": {"asset_id": LOGO_ID, "width": 0.5, "opacity": 10},
        }
    )
    assert spec.speed == 0.5
    assert len(spec.texts) == 5


def test_the_hash_is_the_edit_not_how_it_was_written() -> None:
    short = EditSpec.model_validate({"preset": "vivid"})
    full = EditSpec.model_validate(EditSpec.model_validate({"preset": "vivid"}).model_dump())
    assert spec_hash(short) == spec_hash(full)
    assert len(spec_hash(short)) == 64
    assert spec_hash(short) != spec_hash(EditSpec.model_validate({"preset": "warm"}))
    assert is_empty(EditSpec())
    assert not is_empty(short)


def test_problems_name_tools_the_media_cant_take() -> None:
    photo_tools = EditSpec.model_validate(
        {"look": "zorro", "enhance": True, "adjust": {"vibrance": 10, "sharpen": 50}}
    )
    assert problems(photo_tools, "video", 10) == [
        ("look", "Looks are for photos."),
        ("enhance", "Auto-enhance is for photos."),
        ("adjust.sharpen", "Sharpen is for photos."),
        ("adjust.vibrance", "Vibrance is for photos."),
    ]
    assert problems(photo_tools, "image", None) == []

    video_tools = EditSpec.model_validate(
        {
            "trim": {"start_s": 1, "end_s": 4},
            "speed": 2,
            "fade_in_s": 1,
            "fade_out_s": 0.5,
            "mute": True,
            "cover_s": 1,
            "texts": [{"text": "a", "start_s": 1}],
        }
    )
    assert [field for field, _ in problems(video_tools, "image", None)] == [
        "trim",
        "speed",
        "fade_in_s",
        "fade_out_s",
        "mute",
        "cover_s",
        "texts.0.start_s",
    ]
    assert problems(video_tools, "video", 10) == []


def test_problems_keep_times_inside_the_clip() -> None:
    spec = EditSpec.model_validate(
        {
            "trim": {"start_s": 2, "end_s": 12.1},
            "fade_in_s": 3,
            "fade_out_s": 3,
            "cover_s": 9,
            "texts": [{"text": "late", "start_s": 9, "end_s": 9.5}, {"text": "long", "end_s": 9}],
        }
    )
    # The video is 8 s long: the trim ends past it, the clip is 6 s (2 to 8).
    assert problems(spec, "video", 8.0) == [
        ("trim.end_s", "The trim ends after the video does."),
        ("cover_s", "Pick a cover inside the clip."),
        ("texts.0.start_s", "The text starts after the clip ends."),
        ("texts.0.end_s", "The text ends after the clip does."),
        ("texts.1.end_s", "The text ends after the clip does."),
    ]
    assert problems(spec, "video", 12.14) == []  # within Cloudinary's rounding
    short = EditSpec.model_validate({"fade_in_s": 3, "fade_out_s": 3})
    assert problems(short, "video", 5) == [("fade_out_s", "The fades are longer than the clip.")]
    assert problems(short, "video", None) == []  # length unknown: the render decides
