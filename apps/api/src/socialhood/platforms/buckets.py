"""Per-account token buckets in Valkey (TR-PL-09).

Sized to Meta's published limits. A caller that cannot take a token gets the seconds to wait;
jobs re-schedule themselves for then, which does not count as a retry. All workers share the
buckets, so adding workers never raises the send rate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

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
    WA_SEND = "wa_send"


SPECS: dict[Bucket, BucketSpec] = {
    Bucket.IG_SEND: BucketSpec(capacity=100, per_second=100),
    Bucket.IG_SEND_MEDIA: BucketSpec(capacity=10, per_second=10),
    Bucket.IG_PRIVATE_REPLY: BucketSpec(capacity=750, per_second=750 / 3600),
    Bucket.IG_CONVERSATIONS: BucketSpec(capacity=2, per_second=2),
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


class TokenBuckets:
    def __init__(self, redis: Redis) -> None:
        self._take = redis.register_script(_TAKE)

    async def take(self, bucket: Bucket, account_id: str, *, now: float | None = None) -> float:
        """Take one token. Return 0 when granted, else the seconds until one is free."""
        spec = SPECS[bucket]
        result = await self._take(
            keys=[f"bucket:{bucket}:{account_id}"],
            args=[spec.capacity, spec.per_second, time.time() if now is None else now],
        )
        return float(result)
