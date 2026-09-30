"""(asset, EditSpec) → a Cloudinary transformation and URL (TR-MED-04; docs/editor-spike.md).

The web has a line-for-line twin (apps/web/src/lib/editor/transform.ts) and both run the golden
fixtures in packages/editor-fixtures/transform-cases.json, so a preview in the browser is the
file that gets published. Change both, then regenerate the fixtures (scripts/editor_fixtures.py).

Components, in order (one effect per component; Cloudinary ignores a second ``e_`` in one):

1. ``so_,eo_``: the trim (video), or ``so_`` of the frame (a video still)
2. ``a_90`` / ``a_180`` / ``a_270``, then ``a_hflip``, ``a_vflip``
3. ``c_crop,w_,h_,x_,y_`` in whole pixels of the rotated media, then ``c_scale,w_,h_`` down to the
   width cap (never up; video dimensions even, as H.264 needs)
4. photos: ``e_improve``, then ``e_art:{look}``
5. adjustments (the preset's plus the owner's, clamped) in ADJUSTMENT_ORDER. The vignette is
   ``e_vignette:{n},b_black``: a photo's vignette is transparent, which JPEG shows as white.
   Warmth is a full-frame wash: a one-space text layer with a translucent background, scaled to
   the frame (``e_tint`` is photo-only)
6. text layers (``l_text:{font}_{px}[_bold][_italic][_center|_right]:{text},co_,b_,bo_`` with
   ``c_limit,w_`` so a long line shrinks to 90% of the width instead of leaving the frame (lines
   break only where the owner typed a newline); then ``fl_layer_apply,fl_no_overflow,g_center,x_,
   y_`` and, on video, ``so_,eo_`` in the trimmed clip's seconds: overlays sit before the speed
   change, so they speed up with it. ``fl_no_overflow`` keeps a layer past the edge from growing
   a photo's canvas)
7. the logo (``l_{public id with : for /},c_scale,w_,o_``), placed like text
8. video: ``e_accelerate``, ``e_fade`` in, ``e_fade`` out (negative), ``e_volume:mute``
9. delivery: ``q_auto`` (JPEG by the extension) or ``vc_h264,ac_aac,q_auto`` (MP4)

Numbers are formatted identically in both languages: pixels by ``floor(v + 0.5)``, seconds with
at most two decimals (``fmt``). Text is percent-encoded byte by byte (UTF-8), with ``,``, ``/``
and ``%`` encoded twice, as Cloudinary's text layers need; characters outside the Basic
Multilingual Plane (most emoji) are dropped: Cloudinary refuses or skips them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from socialhood.media.editor.spec import (
    ADJUSTMENT_ORDER,
    ADJUSTMENTS,
    ASPECTS,
    COOL_RGB,
    FONTS,
    MAX_WIDTH,
    PHOTO_ONLY_ADJUSTMENTS,
    PRESETS,
    SPEEDS,
    TEXT_MAX_WIDTH,
    TEXT_PADDING,
    WARM_RGB,
    WARMTH_MAX_ALPHA,
    EditSpec,
    Kind,
    TextLayer,
)

DELIVERY_BASE = "https://res.cloudinary.com"
IMAGE_DELIVERY = "q_auto"
VIDEO_DELIVERY = "vc_h264,ac_aac,q_auto"


class TransformError(ValueError):
    """The asset can't be edited (no dimensions) or the spec names a logo without its file."""


@dataclass(frozen=True)
class AssetMeta:
    """What the builder needs of a media asset (media_assets, or the web's PostAsset)."""

    cloud_name: str
    public_id: str
    resource_type: Kind
    width: int
    height: int
    duration_s: float | None = None


@dataclass(frozen=True)
class Built:
    """A transformation and its delivery URL, with the output's size (and, for video, length)."""

    kind: Kind
    transformation: str
    format: Literal["jpg", "mp4"]
    url: str
    width: int
    height: int
    duration_s: float | None = None


# ---------------------------------------------------------------- numbers and text


def rhu(value: float) -> int:
    """Round half up: the same in Python and JavaScript (Math.floor(v + 0.5))."""
    return math.floor(value + 0.5)


def fmt(value: float) -> str:
    """A time or fraction with at most two decimals and no trailing zeros ("1.5", "2", "0.25")."""
    hundredths = rhu(value * 100)
    sign = "-" if hundredths < 0 else ""
    whole, frac = divmod(abs(hundredths), 100)
    if frac == 0:
        return f"{sign}{whole}"
    return f"{sign}{whole}.{frac:02d}".rstrip("0")


_UNRESERVED = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")
_TWICE = {ord(","): "%252C", ord("/"): "%252F", ord("%"): "%2525"}


def drawable(text: str) -> str:
    """The text without characters Cloudinary can't draw (outside the BMP, lone surrogates)."""
    return "".join(ch for ch in text if ord(ch) <= 0xFFFF and not 0xD800 <= ord(ch) <= 0xDFFF)


def encode_text(text: str) -> str:
    out: list[str] = []
    for byte in drawable(text).encode("utf-8"):
        if byte in _UNRESERVED:
            out.append(chr(byte))
        elif byte in _TWICE:
            out.append(_TWICE[byte])
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def _alpha(percent: float) -> str:
    return f"{rhu(percent * 255 / 100):02X}"


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def overlay_id(public_id: str) -> str:
    """A public id as an overlay (``l_``) names it: folders separated by colons."""
    return public_id.replace("/", ":")


# ---------------------------------------------------------------- geometry


@dataclass(frozen=True)
class Frame:
    """Source size after rotation, the crop inside it, and the output size."""

    width: int  # rotated source
    height: int
    crop_x: int
    crop_y: int
    crop_w: int
    crop_h: int
    out_w: int
    out_h: int


def _even(value: int) -> int:
    return max(value - value % 2, 2)


def frame(asset: AssetMeta, spec: EditSpec) -> Frame:
    """The crop rectangle (whole pixels of the rotated media) and the output size."""
    if asset.width <= 0 or asset.height <= 0:
        raise TransformError("The media has no dimensions, so it can't be edited.")
    video = asset.resource_type == "video"
    w, h = (asset.height, asset.width) if spec.rotate in (90, 270) else (asset.width, asset.height)
    crop = spec.crop
    if crop is None:
        cw, ch, cx, cy = w, h, 0, 0
    else:
        if crop.aspect == "original":
            bw, bh = float(w), float(h)
        else:
            aw, ah = ASPECTS[crop.aspect]
            if w * ah > h * aw:  # wider than the aspect: full height
                bw, bh = h * aw / ah, float(h)
            else:
                bw, bh = float(w), w * ah / aw
        cw = min(max(rhu(bw / crop.zoom), 1), w)
        ch = min(max(rhu(bh / crop.zoom), 1), h)
        if video:
            cw, ch = min(_even(cw), w), min(_even(ch), h)
        cx = _clamp(rhu(crop.x * w - cw / 2), 0, w - cw)
        cy = _clamp(rhu(crop.y * h - ch / 2), 0, h - ch)
    cap = MAX_WIDTH[asset.resource_type]
    if cw <= cap:
        ow, oh = cw, ch
    else:
        ow = cap
        oh = rhu(cap * ch / cw)
    if video:
        ow, oh = _even(ow), _even(oh)
    return Frame(w, h, cx, cy, cw, ch, ow, oh)


def _geometry(spec: EditSpec, f: Frame) -> list[str]:
    parts: list[str] = []
    if spec.rotate:
        parts.append(f"a_{spec.rotate}")
    if spec.flip_h:
        parts.append("a_hflip")
    if spec.flip_v:
        parts.append("a_vflip")
    if (f.crop_w, f.crop_h) != (f.width, f.height):
        parts.append(f"c_crop,w_{f.crop_w},h_{f.crop_h},x_{f.crop_x},y_{f.crop_y}")
    if (f.out_w, f.out_h) != (f.crop_w, f.crop_h):
        parts.append(f"c_scale,w_{f.out_w},h_{f.out_h}")
    return parts


# ---------------------------------------------------------------- colour


def effective_adjustments(spec: EditSpec, kind: Kind) -> dict[str, int]:
    """The preset's adjustments plus the owner's, clamped; photo-only ones dropped on video."""
    base = PRESETS.get(spec.preset or "", {})
    values: dict[str, int] = {}
    for name in ADJUSTMENT_ORDER:
        if kind == "video" and name in PHOTO_ONLY_ADJUSTMENTS:
            continue
        low, high = ADJUSTMENTS[name]
        value = _clamp(base.get(name, 0) + getattr(spec.adjust, name), low, high)
        if value:
            values[name] = value
    return values


def _warmth(value: int, f: Frame) -> list[str]:
    rgb = WARM_RGB if value > 0 else COOL_RGB
    alpha = f"{rhu(abs(value) * WARMTH_MAX_ALPHA / 100):02X}"
    return [
        f"l_text:Arial_20:%20,b_rgb:{rgb}{alpha}",
        f"c_scale,w_{f.out_w},h_{f.out_h}",
        "fl_layer_apply",
    ]


def _colour(spec: EditSpec, kind: Kind, f: Frame) -> list[str]:
    parts: list[str] = []
    if kind == "image":
        if spec.enhance:
            parts.append("e_improve")
        if spec.look:
            parts.append(f"e_art:{spec.look}")
    for name, value in effective_adjustments(spec, kind).items():
        if name == "warmth":
            parts += _warmth(value, f)
        elif name == "vignette":
            # A photo's vignette fades the edges to transparent, which a JPEG shows as white;
            # b_black makes it the dark vignette video gets.
            parts.append(f"e_vignette:{value},b_black")
        else:
            parts.append(f"e_{name}:{value}")
    return parts


# ---------------------------------------------------------------- overlays


def _offset(fraction: float, size: int) -> int:
    return rhu((fraction - 0.5) * size)


def _placement(x: float, y: float, f: Frame) -> str:
    parts = ["fl_layer_apply", "fl_no_overflow", "g_center"]
    dx, dy = _offset(x, f.out_w), _offset(y, f.out_h)
    if dx:
        parts.append(f"x_{dx}")
    if dy:
        parts.append(f"y_{dy}")
    return ",".join(parts)


def _text(layer: TextLayer, f: Frame, *, timing: bool) -> list[str]:
    px = max(rhu(layer.size * f.out_w), 8)
    style = f"{encode_text(FONTS[layer.font])}_{px}"
    if layer.bold:
        style += "_bold"
    if layer.italic:
        style += "_italic"
    if layer.align != "left":
        style += f"_{layer.align}"
    params = [f"l_text:{style}:{encode_text(layer.text)}", f"co_rgb:{layer.color[1:].upper()}"]
    if layer.background is not None:
        box = f"rgb:{layer.background[1:].upper()}{_alpha(layer.background_opacity)}"
        params.append(f"b_{box}")
        params.append(f"bo_{max(rhu(px * TEXT_PADDING), 1)}px_solid_{box}")
    params += ["c_limit", f"w_{max(rhu(f.out_w * TEXT_MAX_WIDTH), 1)}"]
    apply = _placement(layer.x, layer.y, f)
    if timing:
        if layer.start_s is not None:
            apply += f",so_{fmt(layer.start_s)}"
        if layer.end_s is not None:
            apply += f",eo_{fmt(layer.end_s)}"
    return [",".join(params), apply]


def _visible_at(layer: TextLayer, at_s: float) -> bool:
    if layer.start_s is not None and at_s < layer.start_s:
        return False
    return not (layer.end_s is not None and at_s >= layer.end_s)


def _logo(spec: EditSpec, f: Frame, logo_public_id: str | None) -> list[str]:
    if spec.logo is None:
        return []
    if not logo_public_id:
        raise TransformError("The logo's file is missing.")
    params = [
        f"l_{overlay_id(logo_public_id)}",
        "c_scale",
        f"w_{max(rhu(spec.logo.width * f.out_w), 1)}",
    ]
    if spec.logo.opacity < 100:
        params.append(f"o_{spec.logo.opacity}")
    return [",".join(params), _placement(spec.logo.x, spec.logo.y, f)]


# ---------------------------------------------------------------- builds


def _url(asset: AssetMeta, transformation: str, ext: str) -> str:
    return (
        f"{DELIVERY_BASE}/{asset.cloud_name}/{asset.resource_type}/upload/"
        f"{transformation}/{asset.public_id}.{ext}"
    )


def clip_length(asset: AssetMeta, spec: EditSpec) -> float | None:
    """Seconds of the trimmed clip, before speed (None when the length isn't known)."""
    if spec.trim is not None:
        end = spec.trim.end_s
        if asset.duration_s is not None:
            end = min(end, asset.duration_s)
        return max(end - spec.trim.start_s, 0.0)
    return asset.duration_s


def build(asset: AssetMeta, spec: EditSpec, *, logo_public_id: str | None = None) -> Built:
    """The rendered file: the edited image (on the fly) or video (rendered eagerly)."""
    f = frame(asset, spec)
    kind = asset.resource_type
    parts: list[str] = []
    if kind == "video" and spec.trim is not None:
        parts.append(f"so_{fmt(spec.trim.start_s)},eo_{fmt(spec.trim.end_s)}")
    parts += _geometry(spec, f)
    parts += _colour(spec, kind, f)
    for layer in spec.texts:
        parts += _text(layer, f, timing=kind == "video")
    parts += _logo(spec, f, logo_public_id)
    duration: float | None = None
    if kind == "video":
        if SPEEDS[spec.speed]:
            parts.append(f"e_accelerate:{SPEEDS[spec.speed]}")
        if spec.fade_in_s > 0:
            parts.append(f"e_fade:{rhu(spec.fade_in_s * 1000)}")
        if spec.fade_out_s > 0:
            parts.append(f"e_fade:-{rhu(spec.fade_out_s * 1000)}")
        if spec.mute:
            parts.append("e_volume:mute")
        parts.append(VIDEO_DELIVERY)
        length = clip_length(asset, spec)
        duration = None if length is None else rhu(length / spec.speed * 100) / 100
        ext: Literal["jpg", "mp4"] = "mp4"
    else:
        parts.append(IMAGE_DELIVERY)
        ext = "jpg"
    transformation = "/".join(parts)
    return Built(
        kind, transformation, ext, _url(asset, transformation, ext), f.out_w, f.out_h, duration
    )


def still(
    asset: AssetMeta,
    spec: EditSpec,
    *,
    at_s: float = 0.0,
    max_width: int | None = None,
    logo_public_id: str | None = None,
) -> Built:
    """A JPEG preview. For a video: the frame ``at_s`` seconds into the trimmed clip, with the
    same crop, colour, logo and the text layers showing at that moment (not speed, fades or
    sound), which is also the Reel cover. For a photo: the edited photo. ``max_width`` scales it
    down for the editor (never up)."""
    f = frame(asset, spec)
    kind = asset.resource_type
    parts: list[str] = []
    if kind == "video":
        start = spec.trim.start_s if spec.trim is not None else 0.0
        parts.append(f"so_{fmt(start + at_s)}")
    parts += _geometry(spec, f)
    parts += _colour(spec, kind, f)
    for layer in spec.texts:
        if kind == "image" or _visible_at(layer, at_s):
            parts += _text(layer, f, timing=False)
    parts += _logo(spec, f, logo_public_id)
    width, height = f.out_w, f.out_h
    if max_width is not None and max_width < width:
        height = rhu(max_width * height / width)
        width = max_width
        parts.append(f"c_scale,w_{width}")
    parts.append(IMAGE_DELIVERY)
    transformation = "/".join(parts)
    return Built("image", transformation, "jpg", _url(asset, transformation, "jpg"), width, height)


def cover(asset: AssetMeta, spec: EditSpec, *, logo_public_id: str | None = None) -> Built | None:
    """The Reel cover (Instagram's cover_url): the still at ``cover_s``; None without one."""
    if asset.resource_type != "video" or spec.cover_s is None:
        return None
    return still(asset, spec, at_s=spec.cover_s, logo_public_id=logo_public_id)
