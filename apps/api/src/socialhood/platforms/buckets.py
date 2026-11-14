"""Per-account token buckets in Valkey (TR-PL-09), and YouTube's daily upload count (C-196).

Sized to Meta's published limits. A caller that cannot take a token gets the seconds to wait;
jobs re-schedule themselves for then, which does not count as a retry. All workers share the
buckets, so adding workers never raises the send rate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from enum import StrEnum
from zoneinfo import ZoneInfo

from redis.asyncio import Redis


@dataclass(frozen=True)
class BucketSpec:
    capacity: float  # burst size
    per_second: float  # refill rate


class Bucket(StrEnum):
    IG_SEND = "ig_send"  # text, links, reactions, stickers
    IG_SEND_MEDIA = "ig_send_media"  # audio and video; images too until T0.9 says otherwise
    IG_PRIVATE_REPLY = "ig_private_reply"
    IG_CONVERSATIONS = "ig_conversations"
    IG_INSIGHTS = "ig_insights"  # live counts and insights for the metric snapshots (FR-ANL-01)
    WA_SEND = "wa_send"


PRIVATE_REPLY_BURST = 20
PRIVATE_REPLIES_PER_HOUR = 750 - PRIVATE_REPLY_BURST

SPECS: dict[Bucket, BucketSpec] = {
    Bucket.IG_SEND: BucketSpec(capacity=100, per_second=100),
    Bucket.IG_SEND_MEDIA: BucketSpec(capacity=10, per_second=10),
    # FR-AUT-10: never more than 750 in any hour. A bucket grants at most its capacity plus an
    # hour's refill in any hour, so a burst of 20 refills at 730 an hour (a 750 burst would allow
    # 1,500 in the first hour of a surge).
    Bucket.IG_PRIVATE_REPLY: BucketSpec(
        capacity=PRIVATE_REPLY_BURST, per_second=PRIVATE_REPLIES_PER_HOUR / 3600
    ),
    Bucket.IG_CONVERSATIONS: BucketSpec(capacity=2, per_second=2),
    # Meta publishes no per-second limit for insight reads, only the rolling 24 h budget of
    # 4,800 x the account's impressions (TR-PL-09), which snapshots use a tiny part of. The bucket
    # paces bursts (a worker catching up after downtime) at the Conversations API's rate.
    Bucket.IG_INSIGHTS: BucketSpec(capacity=10, per_second=2),
    Bucket.WA_SEND: BucketSpec(capacity=80, per_second=80),
}

# Tokens and last refill time in one hash; refill, then take one if available.
_TAKE = """
local key = KEYS[1]
local capacity, rate, now = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
local state = redis.call('HMGET', key, 'tokens', 'at')
local tokens = tonumber(state[1]) or capacity
local at = tonumber(state[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - at) * rate)
local wait = 0
if tokens >= 1 then
  tokens = tokens - 1
else
  wait = (1 - tokens) / rate
end
redis.call('HSET', key, 'tokens', tokens, 'at', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) + 60)
return tostring(wait)
"""

# The same, taking up to ARGV[4] tokens at once: returns {taken, seconds until the next token
# after these (0 while one is left)}.
_TAKE_MANY = """
local key = KEYS[1]
local capacity, rate, now = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
local want = tonumber(ARGV[4])
local state = redis.call('HMGET', key, 'tokens', 'at')
local tokens = tonumber(state[1]) or capacity
local at = tonumber(state[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - at) * rate)
local taken = math.max(0, math.min(want, math.floor(tokens)))
tokens = tokens - taken
local wait = 0
if tokens < 1 then
  wait = (1 - tokens) / rate
end
redis.call('HSET', key, 'tokens', tokens, 'at', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) + 60)
return {taken, tostring(wait)}
"""


class TokenBuckets:
    def __init__(self, redis: Redis) -> None:
        self._take = redis.register_script(_TAKE)
        self._take_many = redis.register_script(_TAKE_MANY)

    async def take(self, bucket: Bucket, account_id: str, *, now: float | None = None) -> float:
        """Take one token. Return 0 when granted, else the seconds until one is free."""
        spec = SPECS[bucket]
        result = await self._take(
            keys=[f"bucket:{bucket}:{account_id}"],
            args=[spec.capacity, spec.per_second, time.time() if now is None else now],
        )
        return float(result)

    async def take_many(
        self, bucket: Bucket, account_id: str, count: int, *, now: float | None = None
    ) -> tuple[int, float]:
        """Take up to ``count`` tokens. Return how many were taken and the seconds until the
        next one is free (0 while one is left), so a caller knows the bucket is empty without
        asking again."""
        spec = SPECS[bucket]
        taken, wait = await self._take_many(
            keys=[f"bucket:{bucket}:{account_id}"],
            args=[spec.capacity, spec.per_second, time.time() if now is None else now, count],
        )
        return int(taken), float(wait)


# ---------------------------------------------------------------- YouTube's daily uploads (C-196)

# videos.insert has a bucket of its own: 100 calls a day for the whole Google Cloud project, so
# for every customer together, reset at midnight Pacific Time (Google's quota day). One upload is
# counted when a session opens, on either route; an unfinished one still counts (Google counted
# the call).
YOUTUBE_UPLOADS = "youtube_uploads"
YOUTUBE_UPLOADS_PER_DAY = 100
GOOGLE_DAY = ZoneInfo("America/Los_Angeles")

_TAKE_DAILY = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
if n > tonumber(ARGV[1]) then
  redis.call('DECR', KEYS[1])
  return 0
end
return n
"""


def google_day(now: datetime) -> date:
    return now.astimezone(GOOGLE_DAY).date()


def next_google_day(now: datetime) -> datetime:
    """When the next quota day starts (midnight Pacific Time), in UTC."""
    day = google_day(now) + timedelta(days=1)
    return datetime.combine(day, dt_time(0), tzinfo=GOOGLE_DAY).astimezone(UTC)


def _daily_key(now: datetime) -> str:
    return f"bucket:{YOUTUBE_UPLOADS}:{google_day(now).isoformat()}"


class YouTubeUploads:
    """The project's videos.insert count for Google's quota day, shared by every worker."""

    def __init__(self, redis: Redis, limit: int | None = None) -> None:
        self.redis = redis
        self.limit = YOUTUBE_UPLOADS_PER_DAY if limit is None else limit
        self._take = redis.register_script(_TAKE_DAILY)

    async def take(self, now: datetime) -> bool:
        """Count one upload; False (nothing counted) when the day's are used up."""
        taken = await self._take(keys=[_daily_key(now)], args=[self.limit, 2 * 86_400])
        return int(taken) > 0

    async def give_back(self, now: datetime) -> None:
        """An upload that never reached Google (refused before or by the call)."""
        key = _daily_key(now)
        if int(await self.redis.get(key) or 0) > 0:
            await self.redis.decr(key)

    async def used(self, now: datetime) -> int:
        return int(await self.redis.get(_daily_key(now)) or 0)

    async def left(self, now: datetime) -> int:
        return max(0, self.limit - await self.used(now))
