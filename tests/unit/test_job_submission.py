import asyncio
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import UploadFile

from obliq_api.services import jobs
from obliq_api.services.jobs import JobService

DOCUMENT = b"%PDF-1.4\nSynthetic job handoff fixture"


async def submit(service):
    return await service.submit(
        UploadFile(file=BytesIO(DOCUMENT), filename="sample.pdf"),
        organisation_id=uuid4(),
        api_key_id=None,
        is_internal=False,
        request_id="test-request",
    )


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    service = JobService(AsyncMock(), AsyncMock(), AsyncMock())
    service.credits = AsyncMock()
    service.credits.reserve.return_value = 1
    return service


async def test_store_failure_does_not_commit_reservation_or_leak_upload(service, tmp_path):
    service.job_store.create_job.side_effect = ConnectionError("store unavailable")

    with pytest.raises(ConnectionError, match="store unavailable"):
        await submit(service)

    service.credits.reserve.assert_awaited_once()
    service.session.commit.assert_not_awaited()
    assert not list(tmp_path.iterdir())


async def test_failed_commit_removes_queued_job_and_worker_file(service, tmp_path):
    service.session.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError, match="commit failed"):
        await submit(service)

    service.job_store.create_job.assert_awaited_once()
    job_id = service.job_store.create_job.await_args.args[0]
    service.job_store.delete_job.assert_awaited_once_with(job_id)
    assert not list(tmp_path.iterdir())


async def test_worker_receives_upload_after_reservation_is_committed(
    service, monkeypatch, tmp_path
):
    finished = asyncio.Event()
    observed = []

    async def process(*, file_path: Path, **kwargs):
        try:
            observed.append(
                (service.session.commit.await_count, file_path.suffix, file_path.read_bytes())
            )
        finally:
            file_path.unlink()
            finished.set()

    monkeypatch.setattr(jobs, "_process_job", process)
    payload = await submit(service)
    await asyncio.wait_for(finished.wait(), timeout=1)
    assert payload["status"] == "queued"
    assert observed == [(1, ".pdf", DOCUMENT)]
    assert not list(tmp_path.iterdir())


async def test_failed_file_handoff_leaves_no_charge_or_partial_file(service, monkeypatch, tmp_path):
    def fail_replace(*args):
        raise OSError("cannot stage upload")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="cannot stage upload"):
        await submit(service)

    service.session.commit.assert_not_awaited()
    service.job_store.create_job.assert_not_awaited()
    assert not list(tmp_path.iterdir())
