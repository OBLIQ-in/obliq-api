"""Client wrapper for obliq-api, modeling how obliq-in-app calls the service."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from httpx import AsyncClient, Response


class ObliqApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(f"[{status_code}] {code}: {message}")
        self.status_code = status_code
        self.code = code
        self.error_message = message
        self.details = details or {}


class ObliqClient:
    """Async client used to interact with obliq-api."""

    def __init__(self, http_client: AsyncClient, api_key: str | None = None):
        self.client = http_client
        self.api_key = api_key

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _handle_error(self, resp: Response) -> None:
        try:
            data = resp.json()
            err = data.get("error", {})
            raise ObliqApiError(
                status_code=resp.status_code,
                code=err.get("code", "unknown_error"),
                message=err.get("message", resp.text),
                details=err.get("details", {}),
            )
        except (ValueError, KeyError):
            resp.raise_for_status()

    async def submit_job(
        self,
        file_bytes: bytes,
        filename: str = "document.pdf",
        content_type: str = "application/pdf",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Submit a document for OCR. Expects 202 Accepted with job id and queued status."""
        files = {"file": (filename, file_bytes, content_type)}
        resp = await self.client.post(
            "/v1/jobs",
            files=files,
            headers=self._headers(idempotency_key=idempotency_key),
        )
        if resp.status_code != 202:
            self._handle_error(resp)
        return resp.json()

    async def get_job_status(self, job_id: str | UUID) -> dict[str, Any]:
        """Get the current processing status of a job."""
        resp = await self.client.get(
            f"/v1/jobs/{job_id}",
            headers=self._headers(),
        )
        if resp.status_code != 200:
            self._handle_error(resp)
        return resp.json()

    async def get_job_result(self, job_id: str | UUID) -> dict[str, Any]:
        """Fetch final OCR results for a completed job."""
        resp = await self.client.get(
            f"/v1/jobs/{job_id}/result",
            headers=self._headers(),
        )
        if resp.status_code != 200:
            self._handle_error(resp)
        return resp.json()

    async def poll_until_complete(
        self,
        job_id: str | UUID,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
    ) -> dict[str, Any]:
        """Poll job status until succeeded, failed, or timed out."""
        start = time.time()
        while time.time() - start < timeout_seconds:
            status_data = await self.get_job_status(job_id)
            status = status_data.get("status")
            if status in ("succeeded", "partial"):
                return await self.get_job_result(job_id)
            if status == "failed":
                raise ObliqApiError(
                    status_code=500,
                    code=status_data.get("error_code") or "job_failed",
                    message=status_data.get("error_message") or "Job processing failed",
                )
            await asyncio.sleep(poll_interval_seconds)

        raise TimeoutError(f"Job {job_id} did not complete within {timeout_seconds}s")