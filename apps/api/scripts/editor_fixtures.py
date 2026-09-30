"""Write the editor's golden fixtures (TR-MED-04): packages/editor-fixtures/transform-cases.json.

Each case is an asset, an EditSpec (as the web would send it: defaults may be left out) and what
the Python builder makes of it: the render, previews (stills) and the Reel cover. pytest
(tests/unit/test_editor_transform.py) and vitest (apps/web/src/lib/editor/transform.test.ts) run
every case, so the two builders give the same string or a suite fails.

The cases live here; the expected values come from media/editor/transform.py. After changing the
builders (both), run from apps/api:

    uv run python scripts/editor_fixtures.py          # rewrite the file
    uv run python scripts/editor_fixtures.py --check  # exit 1 if it is out of date
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support.editor import FIXTURES as OUT
from tests.support.editor import lenient_spec

from socialhood.media.editor.spec import EditSpec, constants
from socialhood.media.editor.transform import AssetMeta, Built, build, cover, still

CLOUD = "sh-demo"
WS = "ws/5c7e1a52-8f3b-4c1e-9d0a-2b6f4e8a9c31/post"
LOGO = f"{WS}/brand-logo_v2"
LOGO_ID = "0b8f6f5e-2f1d-4d57-a0f4-7c55b3c1d9e2"


def asset(name: str, kind: str, w: int, h: int, duration: float | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "cloud_name": CLOUD,
        "public_id": f"{WS}/{name}",
        "resource_type": kind,
        "width": w,
        "height": h,
    }
    if kind == "video":
        meta["duration_s"] = duration
    return meta


PHONE = asset("phone-photo", "image", 4032, 3024)
PORTRAIT = asset("portrait", "image", 1080, 1350)
SMALL = asset("small-square", "image", 640, 640)
PANORAMA = asset("panorama", "image", 3000, 1000)
LANDSCAPE_VIDEO = asset("landscape-clip", "video", 1920, 1080, 30.5)
PORTRAIT_VIDEO = asset("portrait-clip", "video", 1080, 1920, 45.2)
SMALL_VIDEO = asset("small-clip", "video", 640, 360, 8.0)
ODD_VIDEO = asset("odd-clip", "video", 1281, 721, 12.34)
UHD_VIDEO = asset("uhd-clip", "video", 3840, 2160, 20.0)
NO_DURATION_VIDEO = asset("no-duration", "video", 1280, 720, None)

HINDI = "नमस्ते दोस्तों"
FIRE = "\U0001f525"

# (name, asset, spec, stills [(at_s, max_width)], with the logo's public id)
CASES: list[tuple[str, dict[str, Any], dict[str, Any], list[tuple[float, int | None]], bool]] = [
    # ---- photos: geometry
    ("image: no edit, a large photo scales to 1440", PHONE, {}, [], False),
    ("image: no edit, a small photo stays as it is", SMALL, {}, [], False),
    ("image: crop 1:1 centred", PHONE, {"crop": {"aspect": "1:1"}}, [], False),
    (
        "image: crop 4:5, zoom 1.5, focus top left",
        PHONE,
        {"crop": {"aspect": "4:5", "zoom": 1.5, "x": 0.1, "y": 0.1}},
        [],
        False,
    ),
    (
        "image: crop 1.91:1 focus bottom",
        PHONE,
        {"crop": {"aspect": "1.91:1", "y": 1.0}},
        [],
        False,
    ),
    (
        "image: crop 9:16 from a panorama",
        PANORAMA,
        {"crop": {"aspect": "9:16", "x": 0.7}},
        [],
        False,
    ),
    (
        "image: original shape, zoom 2, focus low left",
        PORTRAIT,
        {"crop": {"aspect": "original", "zoom": 2, "x": 0.2, "y": 0.8}},
        [],
        False,
    ),
    ("image: rotate 90", PHONE, {"rotate": 90}, [], False),
    (
        "image: rotate 270 then crop 4:5",
        PHONE,
        {"rotate": 270, "crop": {"aspect": "4:5"}},
        [],
        False,
    ),
    ("image: rotate 180 and flip across", PORTRAIT, {"rotate": 180, "flip_h": True}, [], False),
    ("image: flip upside down", SMALL, {"flip_v": True}, [], False),
    (
        "image: crop zoom 4 on a small photo",
        SMALL,
        {"crop": {"aspect": "1:1", "zoom": 4, "x": 0.9, "y": 0.9}},
        [],
        False,
    ),
    # ---- photos: colour
    ("image: preset vivid", PORTRAIT, {"preset": "vivid"}, [], False),
    ("image: preset mono", PORTRAIT, {"preset": "mono"}, [], False),
    ("image: preset golden (warmth wash)", PORTRAIT, {"preset": "golden"}, [], False),
    ("image: preset fade", SMALL, {"preset": "fade"}, [], False),
    ("image: preset dramatic", SMALL, {"preset": "dramatic"}, [], False),
    (
        "image: every adjustment at its limit",
        PORTRAIT,
        {
            "adjust": {
                "brightness": -99,
                "contrast": 100,
                "saturation": -100,
                "gamma": -50,
                "vibrance": 100,
                "warmth": -100,
                "vignette": 100,
                "sharpen": 400,
            }
        },
        [],
        False,
    ),
    (
        "image: preset plus own warmth clamps at 100",
        PORTRAIT,
        {"preset": "warm", "adjust": {"warmth": 80, "saturation": -10}},
        [],
        False,
    ),
    ("image: artistic look", PORTRAIT, {"look": "zorro"}, [], False),
    ("image: auto-enhance and a look", PHONE, {"enhance": True, "look": "hokusai"}, [], False),
    (
        "image: auto-enhance and sharpen",
        SMALL,
        {"enhance": True, "adjust": {"sharpen": 80}},
        [],
        False,
    ),
    # ---- photos: text
    ("image: text with defaults", PORTRAIT, {"texts": [{"text": "New arrivals"}]}, [], False),
    (
        "image: bold italic left text on an 80% box",
        PORTRAIT,
        {
            "texts": [
                {
                    "text": "Weekend sale",
                    "font": "montserrat",
                    "size": 0.08,
                    "color": "#ffd700",
                    "bold": True,
                    "italic": True,
                    "align": "left",
                    "background": "#000000",
                    "background_opacity": 80,
                    "x": 0.3,
                    "y": 0.15,
                }
            ]
        },
        [],
        False,
    ),
    (
        "image: text escaping of comma, slash and percent",
        SMALL,
        {"texts": [{"text": "Sale, today/tomorrow: 50% off"}]},
        [],
        False,
    ),
    (
        "image: text with accents",
        SMALL,
        {"texts": [{"text": "Café crème, jalapeño, Ünïcode"}]},
        [],
        False,
    ),
    (
        "image: Hindi text in Poppins",
        PORTRAIT,
        {"texts": [{"text": HINDI, "font": "poppins", "size": 0.07, "background": "#1A1A1A"}]},
        [],
        False,
    ),
    (
        "image: emoji outside the BMP are dropped, BMP symbols kept",
        SMALL,
        {"texts": [{"text": f"Hot {FIRE} deals ❤ ★"}]},
        [],
        False,
    ),
    (
        "image: two lines and URL specials",
        PORTRAIT,
        {"texts": [{"text": "Line one #1?\nQ&A: yes_no ~ (100) +5 = 'ok' \"q\" <b>"}]},
        [],
        False,
    ),
    (
        "image: five layers, every font",
        PHONE,
        {
            "texts": [
                {"text": "Poppins", "font": "poppins", "x": 0.5, "y": 0.1},
                {"text": "Playfair", "font": "playfair", "x": 0.5, "y": 0.3, "italic": True},
                {"text": "Pacifico", "font": "pacifico", "x": 0.5, "y": 0.5, "size": 0.1},
                {"text": "ANTON", "font": "anton", "x": 0.5, "y": 0.7, "color": "#FF0000"},
                {"text": "Marker", "font": "marker", "x": 0.5, "y": 0.9, "align": "right"},
            ]
        },
        [],
        False,
    ),
    (
        "image: montserrat text pinned to a corner",
        PORTRAIT,
        {"texts": [{"text": "Top right", "font": "montserrat", "align": "right", "x": 1, "y": 0}]},
        [],
        False,
    ),
    (
        "image: text timing is ignored on photos",
        SMALL,
        {"texts": [{"text": "Always here", "start_s": 1, "end_s": 2}]},
        [],
        False,
    ),
    ("image: logo with defaults", PORTRAIT, {"logo": {"asset_id": LOGO_ID}}, [], True),
    (
        "image: logo small, faint, top left",
        PHONE,
        {"logo": {"asset_id": LOGO_ID, "width": 0.1, "opacity": 50, "x": 0.08, "y": 0.06}},
        [],
        True,
    ),
    (
        "image: everything at once",
        PHONE,
        {
            "rotate": 90,
            "flip_h": True,
            "crop": {"aspect": "4:5", "zoom": 1.2, "x": 0.4, "y": 0.6},
            "preset": "retro",
            "adjust": {"brightness": 10, "vibrance": 20},
            "look": "aurora",
            "enhance": True,
            "texts": [
                {
                    "text": "Sale, 20% off",
                    "font": "anton",
                    "size": 0.09,
                    "y": 0.85,
                    "background": "#000000",
                }
            ],
            "logo": {"asset_id": LOGO_ID, "width": 0.15, "opacity": 90},
        },
        [(0, 540)],
        True,
    ),
    (
        "image: video-only fields are ignored on photos",
        SMALL,
        {
            "trim": {"start_s": 1, "end_s": 4},
            "speed": 2,
            "mute": True,
            "fade_in_s": 1,
            "cover_s": 2,
        },
        [],
        False,
    ),
    ("image: preview scaled to 540", PHONE, {"preset": "cool"}, [(0, 540)], False),
    (
        "image: preview wider than the photo stays full size",
        SMALL,
        {"preset": "bright"},
        [(0, 1080)],
        False,
    ),
    # ---- carousel items: one look applied to every photo, each with its own crop
    (
        "carousel item 1: photo 4:5 with the shared look",
        PHONE,
        {"crop": {"aspect": "4:5"}, "preset": "noir", "adjust": {"contrast": 5}},
        [],
        False,
    ),
    (
        "carousel item 2: photo 4:5 with the shared look, other focus",
        PORTRAIT,
        {"crop": {"aspect": "4:5", "x": 0.3}, "preset": "noir", "adjust": {"contrast": 5}},
        [],
        False,
    ),
    (
        "carousel item 3: video 4:5 trimmed, same preset",
        LANDSCAPE_VIDEO,
        {
            "crop": {"aspect": "4:5"},
            "preset": "noir",
            "adjust": {"contrast": 5},
            "trim": {"start_s": 2, "end_s": 17.5},
        },
        [(0, 360)],
        False,
    ),
    # ---- videos
    ("video: no edit", LANDSCAPE_VIDEO, {}, [(0, None)], False),
    (
        "video: trim",
        LANDSCAPE_VIDEO,
        {"trim": {"start_s": 1.25, "end_s": 11.75}},
        [(2, 540)],
        False,
    ),
    (
        "video: trim and 2x",
        SMALL_VIDEO,
        {"trim": {"start_s": 1, "end_s": 7}, "speed": 2},
        [],
        False,
    ),
    ("video: half speed", SMALL_VIDEO, {"speed": 0.5}, [], False),
    (
        "video: 1.5x with fades",
        SMALL_VIDEO,
        {"speed": 1.5, "fade_in_s": 0.5, "fade_out_s": 1.25},
        [],
        False,
    ),
    ("video: mute", PORTRAIT_VIDEO, {"mute": True}, [], False),
    (
        "video: reel crop 9:16 from landscape",
        LANDSCAPE_VIDEO,
        {"crop": {"aspect": "9:16"}},
        [(1, 540)],
        False,
    ),
    (
        "video: crop 1:1 zoom 1.3 off centre",
        LANDSCAPE_VIDEO,
        {"crop": {"aspect": "1:1", "zoom": 1.3, "x": 0.25, "y": 0.4}},
        [],
        False,
    ),
    (
        "video: rotate 90 then crop 4:5",
        LANDSCAPE_VIDEO,
        {"rotate": 90, "crop": {"aspect": "4:5"}},
        [],
        False,
    ),
    ("video: flip across", SMALL_VIDEO, {"flip_h": True}, [], False),
    (
        "video: preset noir plus brightness",
        PORTRAIT_VIDEO,
        {"preset": "noir", "adjust": {"brightness": 15}},
        [(3.5, 540)],
        False,
    ),
    ("video: preset warm (warmth wash)", SMALL_VIDEO, {"preset": "warm"}, [], False),
    (
        "video: preset cool and golden-ish own warmth",
        SMALL_VIDEO,
        {"preset": "cool", "adjust": {"warmth": 90}},
        [],
        False,
    ),
    (
        "video: photo-only tools are ignored",
        SMALL_VIDEO,
        {
            "look": "zorro",
            "enhance": True,
            "adjust": {"vibrance": 50, "sharpen": 100, "contrast": 10},
        },
        [],
        False,
    ),
    (
        "video: timed and untimed text",
        LANDSCAPE_VIDEO,
        {
            "trim": {"start_s": 5, "end_s": 20},
            "texts": [
                {"text": "Always", "y": 0.1},
                {
                    "text": "Only 2 to 4.5 s",
                    "start_s": 2,
                    "end_s": 4.5,
                    "background": "#FFFFFF",
                    "color": "#000000",
                },
            ],
        },
        [(1, 540), (3, 540), (4.5, 540)],
        False,
    ),
    (
        "video: text from 3 s to the end",
        SMALL_VIDEO,
        {"texts": [{"text": "Swipe up, now/later", "start_s": 3}]},
        [(2.99, None), (3, None)],
        False,
    ),
    (
        "video: logo",
        PORTRAIT_VIDEO,
        {"logo": {"asset_id": LOGO_ID, "opacity": 70}},
        [(0, None)],
        True,
    ),
    (
        "video: a full reel",
        LANDSCAPE_VIDEO,
        {
            "trim": {"start_s": 3.5, "end_s": 18.25},
            "crop": {"aspect": "9:16", "x": 0.62},
            "preset": "golden",
            "adjust": {"contrast": 12, "vignette": 20},
            "texts": [
                {
                    "text": "Hot & fresh, 50% off",
                    "font": "anton",
                    "size": 0.1,
                    "y": 0.2,
                    "start_s": 0.5,
                    "end_s": 6,
                },
                {
                    "text": HINDI,
                    "font": "poppins",
                    "y": 0.8,
                    "background": "#000000",
                    "background_opacity": 50,
                },
            ],
            "logo": {"asset_id": LOGO_ID, "width": 0.12, "x": 0.85, "y": 0.08},
            "speed": 1.5,
            "fade_in_s": 0.5,
            "fade_out_s": 1,
            "mute": True,
            "cover_s": 2.4,
        },
        [(0, 540), (6, 540)],
        True,
    ),
    ("video: odd dimensions become even", ODD_VIDEO, {"preset": "bright"}, [], False),
    (
        "video: odd dimensions cropped 4:5",
        ODD_VIDEO,
        {"crop": {"aspect": "4:5", "x": 0.33}},
        [],
        False,
    ),
    (
        "video: portrait 1080 wide needs no scale",
        PORTRAIT_VIDEO,
        {"adjust": {"saturation": 30}},
        [],
        False,
    ),
    ("video: 4K scales to 1080 wide", UHD_VIDEO, {"adjust": {"gamma": 20}}, [(10, 720)], False),
    ("video: cover without a trim", SMALL_VIDEO, {"cover_s": 3.33}, [], False),
    (
        "video: unknown length with a trim",
        NO_DURATION_VIDEO,
        {"trim": {"start_s": 0, "end_s": 9.5}, "speed": 2},
        [],
        False,
    ),
    ("video: unknown length without a trim", NO_DURATION_VIDEO, {"speed": 1.5}, [], False),
]


def _built(b: Built) -> dict[str, Any]:
    out = asdict(b)
    if out.get("duration_s") is None:
        out.pop("duration_s")
    return out


def render() -> dict[str, Any]:
    cases = []
    for name, meta, raw, stills, with_logo in CASES:
        a = AssetMeta(**meta)
        try:
            EditSpec.model_validate(raw)
            valid = True
        except ValidationError:
            valid = False  # the API refuses it; the builders still agree on it
        spec = lenient_spec(raw)
        logo = LOGO if with_logo else None
        made = cover(a, spec, logo_public_id=logo)
        case: dict[str, Any] = {"name": name, "asset": meta, "spec": raw, "valid": valid}
        if with_logo:
            case["logo_public_id"] = logo
        case["expect"] = {
            "build": _built(build(a, spec, logo_public_id=logo)),
            "stills": [
                {
                    "at_s": at,
                    "max_width": width,
                    **_built(still(a, spec, at_s=at, max_width=width, logo_public_id=logo)),
                }
                for at, width in stills
            ],
            "cover": None if made is None else _built(made),
        }
        cases.append(case)
    return {
        "about": (
            "Golden cases for the editor's transformation builders (TR-MED-04). Generated by "
            "apps/api/scripts/editor_fixtures.py from the Python builder; the Python and "
            "TypeScript builders must both reproduce every expect block. Do not edit by hand."
        ),
        "constants": constants(),
        "cases": cases,
    }


def main() -> None:
    text = json.dumps(render(), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT} is out of date; run scripts/editor_fixtures.py")
            raise SystemExit(1)
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(CASES)} cases to {OUT}")


if __name__ == "__main__":
    main()
