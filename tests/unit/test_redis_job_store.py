from uuid import uuid4

import fakeredis.aioredis
import pytest

from obliq_api.stores.redis_job_store import RedisJobStore


@pytest.fixture
async def store():
    store = RedisJobStore()
    store._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield store
    finally:
        await store.close()


async def test_status_transitions_keep_original_deadline(store):
    job_id = uuid4()
    await store.create_job(job_id, {"status": "queued", "request_id": "sample"}, ttl=120)
    key = store._key(job_id)
    deadline = await store._client.pexpiretime(key)

    for status in ["processing", "succeeded"]:
        await store.update_job(job_id, {"status": status})
        assert await store._client.pexpiretime(key) == deadline
        assert await store.get_job(job_id) == {"status": status, "request_id": "sample"}


async def test_explicit_ttl_replaces_deadline_but_missing_job_stays_missing(store):
    job_id = uuid4()
    await store.create_job(job_id, {"status": "queued"}, ttl=10)
    await store.update_job(job_id, {"status": "processing"}, ttl=120)
    assert 119 <= await store._client.ttl(store._key(job_id)) <= 120

    await store.delete_job(job_id)
    await store.update_job(job_id, {"status": "succeeded"}, ttl=120)
    assert await store.get_job(job_id) is None


async def test_job_removed_during_update_is_not_recreated(store, monkeypatch):
    job_id = uuid4()
    await store.create_job(job_id, {"status": "queued"}, ttl=120)
    get_job = store.get_job

    async def read_then_remove(job_id):
        job = await get_job(job_id)
        await store.delete_job(job_id)
        return job

    monkeypatch.setattr(store, "get_job", read_then_remove)
    await store.update_job(job_id, {"status": "processing"})
    assert await get_job(job_id) is None
