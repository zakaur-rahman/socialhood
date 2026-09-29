"""The publishing rules without a database (§5.7 format rules, FR-PUB-01, FR-PUB-02, FR-PUB-09,
FR-PUB-10, FR-PUB-12, TR-MED-02): formats, counting hashtags and mentions, hashtag normalisation,
media file limits, the checklist's order and field names, weekly posting times across daylight
saving changes, thumbnails, and AI answers kept within the caption limits."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from socialhood.models.media import MediaAsset
from socialhood.schemas.publishing import CHECKLIST_KEYS
from socialhood.services import captions
from socialhood.services.scheduled_posts import rules, slots, views
from socialhood.services.scheduled_posts.rules import AssetFacts, PostFacts, TargetFacts

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
MB = 1024 * 1024


def _image(width: int = 1080, height: int = 1350, **values: object) -> AssetFacts:
    base: dict[str, object] = {
        "resource_type": "image",
        "format": "jpg",
        "bytes": 200_000,
        "width": width,
        "height": height,
        "duration_s": None,
    }
    return AssetFacts(**{**base, **values})  # type: ignore[arg-type]


def _video(duration_s: float = 20.0, **values: object) -> AssetFacts:
    base: dict[str, object] = {
        "resource_type": "video",
        "format": "mp4",
        "bytes": 20 * MB,
        "width": 1080,
        "height": 1920,
        "duration_s": duration_s,
    }
    return AssetFacts(**{**base, **values})  # type: ignore[arg-type]


def _target(**values: object) -> TargetFacts:
    base: dict[str, object] = {
        "handle": "@maple.bakery",
        "status": "active",
        "can_publish": True,
        "caption_override": None,
        "recent_posts": 0,
    }
    return TargetFacts(**{**base, **values})  # type: ignore[arg-type]


def _post(**values: object) -> PostFacts:
    base: dict[str, object] = {
        "targets": [_target()],
        "assets": [_image()],
        "caption": "Fresh bread #sourdough",
        "first_comment": None,
        "publish_at": None,
    }
    return PostFacts(**{**base, **values})  # type: ignore[arg-type]


# ---------------------------------------------------------------- formats (§5.7)


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        ([], None),
        (["image"], "image"),
        (["video"], "reel"),
        (["image", "image"], "carousel"),
        (["video"] * 10, "carousel"),
        (["image"] * 11, None),
        (["raw"], None),
        (["image", "raw"], None),
    ],
)
def test_formats(kinds: list[str], expected: str | None) -> None:
    assert rules.derive_format(kinds) == expected


# ---------------------------------------------------------------- hashtags and mentions


def test_hashtags_and_mentions_are_counted_like_instagram() -> None:
    text = "New in! #Summer #sale #sale @maple.bakery write to hi@maple.in #日本 ##double"
    assert rules.count_hashtags(text) == 5
    assert rules.hashtags_in(text) == ["summer", "sale", "sale", "日本", "double"]
    assert rules.count_mentions(text) == 1
    assert rules.count_hashtags(None) == 0


def test_hindi_and_other_indic_hashtags_count_whole() -> None:
    """Vowel signs and viramas are combining marks, which ``\\w`` leaves out: a Hindi hashtag
    must not be cut at its first one."""
    text = "दिवाली मुबारक #दिवाली2026 #हिंदी_पोस्ट #नमस्ते! #ਪੰਜਾਬ #தமிழ்"
    assert rules.hashtags_in(text) == ["दिवाली2026", "हिंदी_पोस्ट", "नमस्ते", "ਪੰਜਾਬ", "தமிழ்"]
    assert rules.count_hashtags(" ".join(f"#दिवाली{i}" for i in range(31))) == 31
    # A nukta typed separately or precomposed is the same hashtag.
    assert rules.normalize_hashtag("#क़िला") == rules.normalize_hashtag("क़िला")


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("#नमस्ते", "नमस्ते"),
        ("#हिंदी_पोस्ट", "हिंदी_पोस्ट"),
        ("नमस् ते", None),
        ("#Summer", "summer"),
        ("  ##Linen_Shirts ", "linen_shirts"),
        ("café", "café"),
        ("two words", None),
        ("#", None),
        ("sale!", None),
    ],
)
def test_hashtags_are_stored_without_hash_and_lowercase(raw: str, stored: str | None) -> None:
    assert rules.normalize_hashtag(raw) == stored


# ---------------------------------------------------------------- media files (TR-MED-02)


@pytest.mark.parametrize(
    ("asset", "problem"),
    [
        (_image(1080, 1350), None),  # 4:5, the tallest photo
        (_image(1080, 566), None),  # 1.91:1, the widest
        (_image(1080, 1080, format="heic"), None),
        (_image(1080, 1400), "Crop this image to between 4:5 (portrait) and 1.91:1 (landscape)."),
        (_image(2000, 1000), "Crop this image to between 4:5 (portrait) and 1.91:1 (landscape)."),
        (_image(format="gif"), "Use a JPEG, PNG, WEBP or HEIC image."),
        (_image(bytes=9 * MB), "Images can be up to 8 MB."),
        (_image(width=None, height=None), None),
        (_video(90), None),
        (_video(90.5), "Videos can be up to 90 seconds."),
        (_video(format="mov"), None),
        (_video(format="webm"), "Use an MP4 or MOV video."),
        (_video(bytes=101 * MB), "Videos can be up to 100 MB."),
        (AssetFacts("raw", "pdf", 1, None, None, None), "Posts can only use images and videos."),
    ],
)
def test_media_file_limits(asset: AssetFacts, problem: str | None) -> None:
    assert rules.asset_problem(asset) == problem


# ---------------------------------------------------------------- the checklist (FR-PUB-10)


def test_a_passing_post_lists_each_check_once_in_order() -> None:
    items = rules.checklist(
        _post(publish_at=NOW + timedelta(hours=1)), now=NOW, publishing_limit=100
    )
    assert [i.key for i in items] == list(CHECKLIST_KEYS)
    assert all(i.ok and i.field is None for i in items)
    assert items[0].message == "Publishing to @maple.bakery"
    assert items[1].message == "Image post"
    assert rules.field_errors(items) == []


def test_publish_at_is_checked_only_when_there_is_a_time_and_asked() -> None:
    soon = _post(publish_at=NOW + timedelta(minutes=4))
    keys = [i.key for i in rules.checklist(_post(), now=NOW, publishing_limit=100)]
    assert "publish_at" not in keys
    [item] = [
        i for i in rules.checklist(soon, now=NOW, publishing_limit=100) if i.key == "publish_at"
    ]
    assert (item.ok, item.field) == (False, "publish_at")
    unchecked = rules.checklist(soon, now=NOW, publishing_limit=100, check_time=False)
    assert all(i.ok for i in unchecked)


def test_each_failing_element_is_its_own_item_named_by_field() -> None:
    post = _post(
        targets=[
            _target(),
            _target(handle="@old.shop", status="needs_reconnect"),
            _target(handle="@gone.shop", status="disconnected"),
            _target(handle="@wa", can_publish=False, caption_override="#a " * 31),
            _target(handle="@busy", recent_posts=100),
        ],
        assets=[_image(), _video(120), _image(2000, 1000)],
        caption="x" * 2201,
        first_comment=" ".join(f"@p{i}" for i in range(25)),
    )

    items = rules.checklist(post, now=NOW, publishing_limit=100)

    failing = [(i.key, i.field) for i in items if not i.ok]
    assert failing == [
        ("accounts", "targets.1"),
        ("accounts", "targets.2"),
        ("accounts", "targets.3"),
        ("media_files", "asset_ids.1"),
        ("media_files", "asset_ids.2"),
        ("caption", "caption"),
        ("hashtags", "targets.3.caption_override"),
        ("publishing_limit", "targets.4"),
    ]
    # Every failing item is a field error with the same name and message.
    assert [(e.field, e.message) for e in rules.field_errors(items)] == [
        (i.field, i.message) for i in items if not i.ok
    ]
    # A first comment's mentions don't count against the caption's 20.
    assert all(i.ok for i in items if i.key == "mentions")


def test_a_post_without_accounts_or_media() -> None:
    items = rules.checklist(_post(targets=[], assets=[]), now=NOW, publishing_limit=100)
    assert [(i.key, i.field) for i in items if not i.ok] == [
        ("accounts", "targets"),
        ("media", "asset_ids"),
    ]


# ---------------------------------------------------------------- posting times (FR-PUB-09)


def test_weekly_times_follow_the_local_clock_across_daylight_saving() -> None:
    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 3, 1, tzinfo=UTC)
    end = datetime(2026, 3, 16, tzinfo=UTC)
    found = slots.occurrences([(2, time(18, 0))], zone, start=start, end=end)  # Wednesdays

    assert [f.astimezone(zone).time() for f in found] == [time(18, 0)] * 2
    # 18:00 EST is 23:00 UTC; after 8 March, 18:00 EDT is 22:00 UTC.
    assert [f.hour for f in found] == [23, 22]
    assert found == sorted(found)


def test_occurrences_stay_in_the_range() -> None:
    zone = ZoneInfo("Asia/Kolkata")
    start = datetime(2026, 9, 28, 12, 30, tzinfo=UTC)  # 18:00 in Kolkata, a Monday
    found = slots.occurrences([(0, time(18, 0))], zone, start=start, end=start + timedelta(7))
    assert found == [start]


def test_a_slot_is_free_unless_a_post_is_within_30_minutes() -> None:
    at = NOW
    assert slots.is_free(at, [])
    assert slots.is_free(at, [at + timedelta(minutes=30), at - timedelta(minutes=30)])
    assert not slots.is_free(at, [at + timedelta(minutes=29)])


def test_an_unknown_zone_is_utc() -> None:
    assert slots.zone("Mars/Olympus").key == "UTC"


# ---------------------------------------------------------------- thumbnails


@pytest.mark.parametrize(
    ("resource_type", "url", "thumbnail"),
    [
        (
            "image",
            "https://res.cloudinary.com/demo/image/upload/v1/ws/w/post/abc.png",
            "https://res.cloudinary.com/demo/image/upload/c_limit,w_480,q_auto/v1/ws/w/post/abc.jpg",
        ),
        (
            "video",
            "https://res.cloudinary.com/demo/video/upload/v1/ws/w/post/clip.mov",
            "https://res.cloudinary.com/demo/video/upload/so_0,c_limit,w_480,q_auto/v1/ws/w/post/clip.jpg",
        ),
        ("image", "https://example.com/pic.png", "https://example.com/pic.png"),
        ("video", "https://example.com/clip.mp4", None),
        ("image", None, None),
    ],
)
def test_thumbnails(resource_type: str, url: str | None, thumbnail: str | None) -> None:
    asset = MediaAsset(resource_type=resource_type, secure_url=url)
    assert views.thumbnail_url(asset) == thumbnail


# ---------------------------------------------------------------- AI answers (FR-PUB-02)


def test_an_ai_caption_is_cut_to_the_limits() -> None:
    caption = "Hello @a @b   there " + " ".join(f"#t{i}" for i in range(40))
    out = captions.within_limits(caption)
    assert rules.count_hashtags(out) == 30
    assert "  " not in out

    hindi = captions.within_limits("नई रोटी " + " ".join(f"#रोटी{i}" for i in range(32)))
    assert rules.hashtags_in(hindi) == [f"रोटी{i}" for i in range(30)]
    assert hindi.endswith("#रोटी29")  # dropped whole: no vowel sign left behind

    long = captions.within_limits("line one\n" + "word " * 500)
    assert len(long) <= 2200
    assert long.endswith("word")
    assert captions.within_limits("x" * 3000) == "x" * 2200


def test_suggested_hashtags_are_normalised_new_and_capped() -> None:
    raw = ["#Bread", "bread", "Pune Food", "sourdough", "#Bakery", "rye", "loaf"]
    assert captions.clean_hashtags(raw, leave_out={"bakery"}, count=3) == [
        "bread",
        "sourdough",
        "rye",
    ]
    hindi = ["#रोटी", "#दिवाली", "पुणे खाना", "#रोटी"]
    assert captions.clean_hashtags(hindi, leave_out={"दिवाली"}, count=5) == ["रोटी"]
