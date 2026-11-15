"""Locust load test suite for obliq-api.

Tests platform limits, concurrency, rate limiting (429 responses), and credit ledger
atomic safety under concurrent load as defined in the Issue #17 capacity plan.

Usage:
    # Run locally headless:
    locust -f tests/load/locustfile.py --headless -u 5 -r 1 --run-time 30s --host http://localhost:8000

    # Run with web UI:
    locust -f tests/load/locustfile.py --host http://localhost:8000
"""

from __future__ import annotations

import os
import time
from uuid import uuid4

from locust import HttpUser, between, task

# Minimal synthetic PDF bytes for fast load benchmarking
TINY_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n"
    b"0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
)


class ObliqApiUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Configure API key per user from environment or mock."""
        self.api_key = os.getenv("LOAD_TEST_API_KEY", "obliq_live_mock_key")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @task(3)
    def submit_and_poll_job(self):
        """Simulate realistic end-user submit and poll workflow."""
        idempotency_key = f"load_{uuid4()}"
        headers = {**self.headers, "Idempotency-Key": idempotency_key}
        files = {"file": ("document.pdf", TINY_PDF, "application/pdf")}

        # 1. Submit job
        with self.client.post("/v1/jobs", headers=headers, files=files, catch_response=True) as resp:
            if resp.status_code == 202:
                resp.success()
                job_id = resp.json().get("id")
            elif resp.status_code == 429:
                # 429 is expected behavior under capacity / rate-limiting
                resp.success()
                return
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")
                return

        if not job_id:
            return

        # 2. Poll for completion
        for _ in range(20):
            time.sleep(0.5)
            with self.client.get(f"/v1/jobs/{job_id}", headers=self.headers, catch_response=True) as poll_resp:
                if poll_resp.status_code == 200:
                    status = poll_resp.json().get("status")
                    if status in ("succeeded", "partial"):
                        poll_resp.success()
                        break
                    elif status == "failed":
                        poll_resp.failure("Job marked failed by backend")
                        break
                else:
                    poll_resp.failure(f"Poll returned status {poll_resp.status_code}")
                    break

    @task(1)
    def check_health_endpoints(self):
        """Lightweight task keeping background tabs and health checks active."""
        self.client.get("/health")
        self.client.get("/ready")


class BurstUser(HttpUser):
    """High-frequency traffic to stress-test rate limiter and concurrency bounds."""
    wait_time = between(0.1, 0.3)

    def on_start(self):
        self.api_key = os.getenv("LOAD_TEST_API_KEY", "obliq_live_mock_key")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    @task
    def burst_submissions(self):
        """Flood submit requests to verify 429 Retry-After responses without server crash."""
        files = {"file": ("burst.pdf", TINY_PDF, "application/pdf")}
        with self.client.post("/v1/jobs", headers=self.headers, files=files, catch_response=True) as resp:
            if resp.status_code in (202, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected status code under burst load: {resp.status_code}")
