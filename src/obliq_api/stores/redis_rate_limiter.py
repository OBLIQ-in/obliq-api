"""Sliding-window rate limiter backed by Redis.

Uses a Lua script executed atomically on the Redis server so the check-and-increment
is race-free across multiple API replicas.

The key structure is:
    {redis_rate_prefix}{key}:{window_start_second}

Each key holds the request count for that one-second slot.  All slots within
the current window are summed; slots outside the window are ignored and left
to expire via their TTL.
"""

from __future__ import annotations

import time

import redis.asyncio as aioredis

from obliq_api.config import get_settings

settings = get_settings()

# Atomic sliding-window Lua script.
# KEYS[1] = rate key prefix (e.g. "obliq:rate:org_id:requests")
# ARGV[1] = current unix timestamp (integer seconds)
# ARGV[2] = window size in seconds
# ARGV[3] = limit (max requests in the window)
# Returns: {current_count, is_allowed}  — 1 = allowed, 0 = denied
_SLIDING_WINDOW_LUA = """
local prefix   = KEYS[1]
local now      = tonumber(ARGV[1])
local window   = tonumber(ARGV[2])
local limit    = tonumber(ARGV[3])

-- Increment the current-second bucket
local cur_key = prefix .. ":" .. now
redis.call("INCR", cur_key)
redis.call("EXPIRE", cur_key, window + 1)

-- Sum all buckets inside the window
local total = 0
for i = 0, window - 1 do
    local bucket = prefix .. ":" .. (now - i)
    local val = redis.call("GET", bucket)
    if val then
        total = total + tonumber(val)
    end
end

if total <= limit then
    return {total, 1}
else
    return {total, 0}
end
"""


class RedisRateLimiter:
    """Implements the RateLimiter protocol using a per-second sliding window in Redis."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._url = redis_url or str(settings.redis_url)
        self._prefix = settings.redis_rate_prefix
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
            )
        return self._client

    async def is_allowed(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        retry_after_seconds is 0 when allowed, otherwise the window size
        (conservative: the client should wait for the full window to pass).
        """
        client = await self._get_client()
        now = int(time.time())
        full_key = f"{self._prefix}{key}"

        try:
            result = await client.eval(  # type: ignore[attr-defined,misc]
                _SLIDING_WINDOW_LUA,
                1,  # number of KEYS
                full_key,
                str(now),
                str(window_seconds),
                str(limit),
            )
            _count, allowed_flag = int(result[0]), int(result[1])
            allowed = allowed_flag == 1
            retry_after = 0 if allowed else window_seconds
            return allowed, retry_after
        except Exception:
            # On Redis failure, fail open (allow the request) so a Redis outage
            # does not take down the API.
            return True, 0

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
