import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from obliq_api.config import get_settings
from obliq_api.protocols import JobStore

settings = get_settings()


class RedisJobStore(JobStore):
    def __init__(self, redis_url: str | None = None) -> None:
        self._url = redis_url or str(settings.redis_url)
        self._prefix = settings.redis_job_prefix
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            # Works with Upstash (rediss://) and local Redis (redis://).
            # Upstash requires TLS; redis-py handles it automatically when the
            # URL scheme is rediss://.
            self._client = redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _key(self, job_id: UUID) -> str:
        return f"{self._prefix}{job_id}"

    def _result_key(self, job_id: UUID) -> str:
        return f"{self._prefix}result:{job_id}"

    async def create_job(
        self,
        job_id: UUID,
        payload: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None:
        await self.connect()
        assert self._client
        data = json.dumps(payload, default=str)
        key = self._key(job_id)
        if ttl:
            await self._client.setex(key, ttl, data)
        else:
            await self._client.set(key, data)

    async def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        await self.connect()
        assert self._client
        raw = await self._client.get(self._key(job_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def update_job(
        self,
        job_id: UUID,
        updates: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None:
        current = await self.get_job(job_id)
        if current is None:
            return
        current.update(updates)
        assert self._client
        # Redis SET discards the existing expiration unless KEEPTTL is set.
        # XX also keeps a job that expired since GET from being recreated.
        await self._client.set(
            self._key(job_id),
            json.dumps(current, default=str),
            xx=True,
            ex=ttl,
            keepttl=ttl is None,
        )

    async def set_result(
        self,
        job_id: UUID,
        result: dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None:
        await self.connect()
        assert self._client
        data = json.dumps(result, default=str)
        key = self._result_key(job_id)
        effective_ttl = ttl or settings.job_result_ttl_seconds
        await self._client.setex(key, effective_ttl, data)

    async def get_result(self, job_id: UUID) -> dict[str, Any] | None:
        await self.connect()
        assert self._client
        raw = await self._client.get(self._result_key(job_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_job(self, job_id: UUID) -> None:
        await self.connect()
        assert self._client
        await self._client.delete(self._key(job_id), self._result_key(job_id))

    async def health_check(self) -> bool:
        try:
            await self.connect()
            assert self._client
            return bool(await self._client.ping())
        except Exception:
            return False
