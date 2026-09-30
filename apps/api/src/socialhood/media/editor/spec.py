"""The edit of one post item, version 1 (FR-PUB-20…27, TR-MED-04; docs/editor-spike.md).

An ``EditSpec`` is plain data: what the owner chose in the editor. The original upload is never
changed; ``media/editor/transform.py`` turns (the asset, the spec) into a Cloudinary transformation
and the rendered file is a derived asset (images on the fly, videos rendered eagerly).

Every constant here has a twin in apps/web/src/lib/editor/spec.ts, and the golden fixtures
(packages/editor-fixtures/transform-cases.json) carry them, so the two builders can't drift.

Field groups:
- both kinds: rotate and flip, crop (aspect, zoom, focus point), preset, adjustments (brightness,
  contrast, saturation, gamma, warmth, vignette), text layers, logo;
- photos only: ``look`` (Cloudinary's artistic filters), ``enhance`` (one-tap auto-enhance), and
  the ``vibrance`` and ``sharpen`` adjustments;
- videos only: trim, speed, fades, mute, the Reel cover and text timing.

The model checks what it can alone (ranges, lengths, characters). What depends on the asset
(photo-only fields on a video, a trim past the video's end) is ``problems(spec, kind,
duration_s)``: the service turns each into a 422 field error.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SPEC_VERSION = 1

# ---------------------------------------------------------------- shared constants

Kind = Literal["image", "video"]
AspectName = Literal["original", "1:1", "4:5", "1.91:1", "9:16"]
# width:height as whole numbers, so crops compare exactly (w * ah vs h * aw).
ASPECTS: dict[str, tuple[int, int]] = {
    "1:1": (1, 1),
    "4:5": (4, 5),
    "1.91:1": (191, 100),
    "9:16": (9, 16),
}
# Output width caps: Instagram takes images up to 1440 px wide; video renders stop at 1080 px (a
# 1080 x 1920 Reel). Smaller sources are never upscaled.
MAX_WIDTH: dict[str, int] = {"image": 1440, "video": 1080}

FontName = Literal["poppins", "montserrat", "playfair", "pacifico", "anton", "marker"]
# Google fonts Cloudinary renders (spike: Bebas Neue, Inter, Space Grotesk and Noto Sans
# Devanagari are refused). Devanagari falls back to a font that has it; Poppins has its own.
FONTS: dict[str, str] = {
    "poppins": "Poppins",
    "montserrat": "Montserrat",
    "playfair": "Playfair Display",
    "pacifico": "Pacifico",
    "anton": "Anton",
    "marker": "Permanent Marker",
}

LookName = Literal[
    "al_dente",
    "athena",
    "audrey",
    "aurora",
    "eucalyptus",
    "fes",
    "frost",
    "hairspray",
    "hokusai",
    "incognito",
    "linen",
    "peacock",
    "primavera",
    "quartz",
    "red_rock",
    "refresh",
    "sizzle",
    "sonnet",
    "ukulele",
    "zorro",
]
# e_art:{look}, photos only (video ignores it). "daenerys" is in Cloudinary's docs but unknown to
# the API (400 "Unknown filter").
LOOKS: tuple[str, ...] = LookName.__args__  # type: ignore[attr-defined]

AdjustmentName = Literal[
    "brightness", "contrast", "saturation", "gamma", "vibrance", "warmth", "vignette", "sharpen"
]
# (min, max) of each adjustment; 0 is "no change" for all of them.
ADJUSTMENTS: dict[str, tuple[int, int]] = {
    "brightness": (-99, 100),  # e_brightness
    "contrast": (-100, 100),  # e_contrast
    "saturation": (-100, 100),  # e_saturation (-100 is black and white)
    "gamma": (-50, 100),  # e_gamma
    "vibrance": (-100, 100),  # e_vibrance, photos only (video ignores it)
    "warmth": (-100, 100),  # a full-frame orange (+) or blue (-) wash; e_tint is photo-only
    "vignette": (0, 100),  # e_vignette
    "sharpen": (0, 400),  # e_sharpen, photos only (video ignores it)
}
PHOTO_ONLY_ADJUSTMENTS = frozenset({"vibrance", "sharpen"})
# The order adjustments apply in (each is its own component: Cloudinary applies one effect per
# component).
ADJUSTMENT_ORDER: tuple[str, ...] = (
    "brightness",
    "contrast",
    "saturation",
    "gamma",
    "vibrance",
    "warmth",
    "vignette",
    "sharpen",
)
WARM_RGB = "FF8C00"
COOL_RGB = "0064FF"
WARMTH_MAX_ALPHA = 64  # of 255, at warmth ±100

PresetName = Literal[
    "vivid", "warm", "cool", "mono", "fade", "noir", "golden", "dramatic", "bright", "retro"
]
# Filters that work on photos and video alike: made only of adjustments video supports. The
# owner's own adjustments add to the preset's (then clamp to the range).
PRESETS: dict[str, dict[str, int]] = {
    "vivid": {"contrast": 15, "saturation": 35},
    "warm": {"saturation": 10, "warmth": 40},
    "cool": {"brightness": 5, "warmth": -40},
    "mono": {"contrast": 20, "saturation": -100},
    "fade": {"brightness": 10, "contrast": -25, "saturation": -20},
    "noir": {"contrast": 45, "saturation": -100, "vignette": 40},
    "golden": {"contrast": 10, "gamma": 10, "warmth": 55},
    "dramatic": {"contrast": 40, "saturation": -10, "vignette": 50},
    "bright": {"brightness": 20, "contrast": -10},
    "retro": {"contrast": -10, "saturation": -30, "warmth": 30, "vignette": 30},
}

# e_accelerate percentages (spike: 8 s at 100 → 4.12 s, 50 → 5.44 s, -50 → 16.04 s).
SPEEDS: dict[float, int] = {0.5: -50, 1: 0, 1.5: 50, 2: 100}

TEXT_MAX_LAYERS = 5
TEXT_MAX_CHARS = 150
TEXT_MAX_LINES = 5
TEXT_SIZE_RANGE = (0.02, 0.2)  # font size as a fraction of the output width
TEXT_MAX_WIDTH = 0.9  # a wider text box (a long line) is scaled down to 90% of the width
TEXT_PADDING = 0.3  # the background box's padding, as a fraction of the font size
LOGO_WIDTH_RANGE = (0.05, 0.5)  # logo width as a fraction of the output width
CROP_MAX_ZOOM = 4.0
FADE_MAX_S = 3.0
TRIM_MIN_S = 1.0
DURATION_SLACK_S = 0.05  # Cloudinary rounds durations; a trim may end this far past the end

Hex = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Seconds = Annotated[float, Field(ge=0.0, le=3600.0)]


class EditModel(BaseModel):
    """Edits reject unknown fields and keep text exactly as typed (no whitespace stripping: the
    web's builder sees the same string)."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- parts


class Crop(EditModel):
    """The frame: the largest rectangle of ``aspect`` inside the (rotated) media, made smaller by
    ``zoom``, centred on the focus point (``x``, ``y``: 0 to 1 across and down) as far as the
    edges allow. ``original`` keeps the media's own shape (zoom still crops in)."""

    aspect: AspectName = "original"
    zoom: float = Field(default=1.0, ge=1.0, le=CROP_MAX_ZOOM)
    x: Fraction = 0.5
    y: Fraction = 0.5


class Adjustments(EditModel):
    """Each 0 by default (no change); ranges in ADJUSTMENTS."""

    brightness: int = Field(default=0, ge=-99, le=100)
    contrast: int = Field(default=0, ge=-100, le=100)
    saturation: int = Field(default=0, ge=-100, le=100)
    gamma: int = Field(default=0, ge=-50, le=100)
    vibrance: int = Field(default=0, ge=-100, le=100)
    warmth: int = Field(default=0, ge=-100, le=100)
    vignette: int = Field(default=0, ge=0, le=100)
    sharpen: int = Field(default=0, ge=0, le=400)


class TextLayer(EditModel):
    """A caption drawn on the media. ``size`` is the font size as a fraction of the output width;
    (``x``, ``y``) is the centre of the text box (0 to 1 across and down). Video only: shown from
    ``start_s`` to ``end_s``, in seconds of the trimmed clip (before any speed change); either
    left out means from the start or to the end."""

    text: str = Field(min_length=1, max_length=TEXT_MAX_CHARS)
    font: FontName = "poppins"
    size: float = Field(default=0.06, ge=TEXT_SIZE_RANGE[0], le=TEXT_SIZE_RANGE[1])
    color: Hex = "#FFFFFF"
    bold: bool = False
    italic: bool = False
    align: Literal["left", "center", "right"] = "center"
    background: Hex | None = None  # a box behind the text
    background_opacity: int = Field(default=60, ge=0, le=100)
    x: Fraction = 0.5
    y: Fraction = 0.5
    start_s: Seconds | None = None
    end_s: Seconds | None = None

    @field_validator("text")
    @classmethod
    def _drawable(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Type some text.")
        for ch in value:
            code = ord(ch)
            if code > 0xFFFF or 0xD800 <= code <= 0xDFFF:
                raise ValueError("Emoji like this can't be drawn on media yet. Remove them.")
            if (code < 0x20 and ch != "\n") or code == 0x7F:
                raise ValueError("Remove the special characters from the text.")
        if value.count("\n") >= TEXT_MAX_LINES:
            raise ValueError(f"Use at most {TEXT_MAX_LINES} lines.")
        return value

    @model_validator(mode="after")
    def _timing(self) -> TextLayer:
        if self.start_s is not None and self.end_s is not None and self.end_s <= self.start_s:
            raise ValueError("The text must end after it starts.")
        return self


class Logo(EditModel):
    """A watermark from an uploaded image (a media asset of this workspace): ``width`` is a
    fraction of the output width; (``x``, ``y``) its centre."""

    asset_id: uuid.UUID
    width: float = Field(default=0.2, ge=LOGO_WIDTH_RANGE[0], le=LOGO_WIDTH_RANGE[1])
    opacity: int = Field(default=100, ge=10, le=100)
    x: Fraction = 0.88
    y: Fraction = 0.92


class Trim(EditModel):
    """The part of the video to keep, in seconds of the original."""

    start_s: Seconds = 0.0
    end_s: Seconds

    @model_validator(mode="after")
    def _order(self) -> Trim:
        if self.end_s - self.start_s < TRIM_MIN_S:
            raise ValueError(f"Keep at least {TRIM_MIN_S:.0f} second of the video.")
        return self


# ---------------------------------------------------------------- the spec


class EditSpec(EditModel):
    """One item's edit (version 1). Everything is optional; an empty spec renders the media as
    Instagram needs it (JPEG up to 1440 px wide, H.264 video up to 1080 px wide)."""

    v: Literal[1] = 1
    rotate: Literal[0, 90, 180, 270] = 0
    flip_h: bool = False
    flip_v: bool = False
    crop: Crop | None = None
    preset: PresetName | None = None
    adjust: Adjustments = Field(default_factory=Adjustments)
    look: LookName | None = None  # photos only
    enhance: bool = False  # photos only: e_improve
    texts: list[TextLayer] = Field(default_factory=list, max_length=TEXT_MAX_LAYERS)
    logo: Logo | None = None
    trim: Trim | None = None  # videos only
    speed: float = Field(default=1.0, json_schema_extra={"enum": [0.5, 1, 1.5, 2]})  # videos only
    fade_in_s: float = Field(default=0.0, ge=0.0, le=FADE_MAX_S)  # videos only
    fade_out_s: float = Field(default=0.0, ge=0.0, le=FADE_MAX_S)  # videos only
    mute: bool = False  # videos only: the original sound is silenced (the track stays)
    cover_s: Seconds | None = None  # videos only: the Reel cover, seconds into the trimmed clip

    @field_validator("speed")
    @classmethod
    def _speed(cls, value: float) -> float:
        if value not in SPEEDS:
            raise ValueError("Choose 0.5x, 1x, 1.5x or 2x.")
        return value


def spec_hash(spec: EditSpec) -> str:
    """media_renders.spec_hash: SHA-256 of the spec's canonical JSON (every field, sorted keys),
    so the same edit of the same asset renders once."""
    canonical = json.dumps(
        spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def is_empty(spec: EditSpec) -> bool:
    """True when the spec changes nothing an owner chose (the item needs no edit)."""
    return spec == EditSpec()


def problems(spec: EditSpec, kind: Kind, duration_s: float | None) -> list[tuple[str, str]]:
    """(field, message) for what the spec can't do to this media: photo-only tools on a video,
    video-only tools on a photo, and times past the (trimmed) video's end."""
    found: list[tuple[str, str]] = []
    if kind == "video":
        if spec.look is not None:
            found.append(("look", "Looks are for photos."))
        if spec.enhance:
            found.append(("enhance", "Auto-enhance is for photos."))
        for name in sorted(PHOTO_ONLY_ADJUSTMENTS):
            if getattr(spec.adjust, name):
                found.append((f"adjust.{name}", f"{name.capitalize()} is for photos."))
        length = _clip_length(spec, duration_s)
        if (
            spec.trim is not None
            and duration_s is not None
            and spec.trim.end_s > duration_s + DURATION_SLACK_S
        ):
            found.append(("trim.end_s", "The trim ends after the video does."))
        if length is not None:
            if spec.fade_in_s + spec.fade_out_s > length:
                found.append(("fade_out_s", "The fades are longer than the clip."))
            if spec.cover_s is not None and spec.cover_s > length:
                found.append(("cover_s", "Pick a cover inside the clip."))
            for i, layer in enumerate(spec.texts):
                if layer.start_s is not None and layer.start_s >= length:
                    found.append((f"texts.{i}.start_s", "The text starts after the clip ends."))
                if layer.end_s is not None and layer.end_s > length + DURATION_SLACK_S:
                    found.append((f"texts.{i}.end_s", "The text ends after the clip does."))
    else:
        for name, value in (
            ("trim", spec.trim is not None),
            ("speed", spec.speed != 1),
            ("fade_in_s", spec.fade_in_s > 0),
            ("fade_out_s", spec.fade_out_s > 0),
            ("mute", spec.mute),
            ("cover_s", spec.cover_s is not None),
        ):
            if value:
                found.append((name, "This is for videos."))
        for i, layer in enumerate(spec.texts):
            if layer.start_s is not None or layer.end_s is not None:
                found.append((f"texts.{i}.start_s", "Text timing is for videos."))
    return found


def _clip_length(spec: EditSpec, duration_s: float | None) -> float | None:
    """Seconds of the trimmed clip (before speed), when known."""
    if spec.trim is not None:
        end = spec.trim.end_s if duration_s is None else min(spec.trim.end_s, duration_s)
        return max(end - spec.trim.start_s, 0.0)
    return duration_s


def constants() -> dict[str, Any]:
    """The shared constants, as the golden fixtures carry them for the web's twin."""
    return {
        "version": SPEC_VERSION,
        "aspects": {k: list(v) for k, v in ASPECTS.items()},
        "max_width": MAX_WIDTH,
        "fonts": FONTS,
        "looks": list(LOOKS),
        "adjustments": {k: list(v) for k, v in ADJUSTMENTS.items()},
        "adjustment_order": list(ADJUSTMENT_ORDER),
        "photo_only_adjustments": sorted(PHOTO_ONLY_ADJUSTMENTS),
        "presets": PRESETS,
        "speeds": {str(k): v for k, v in SPEEDS.items()},
        "warm_rgb": WARM_RGB,
        "cool_rgb": COOL_RGB,
        "warmth_max_alpha": WARMTH_MAX_ALPHA,
        "text_max_layers": TEXT_MAX_LAYERS,
        "text_max_chars": TEXT_MAX_CHARS,
        "text_max_lines": TEXT_MAX_LINES,
        "text_size_range": list(TEXT_SIZE_RANGE),
        "text_max_width": TEXT_MAX_WIDTH,
        "text_padding": TEXT_PADDING,
        "logo_width_range": list(LOGO_WIDTH_RANGE),
        "crop_max_zoom": CROP_MAX_ZOOM,
        "fade_max_s": FADE_MAX_S,
        "trim_min_s": TRIM_MIN_S,
    }
