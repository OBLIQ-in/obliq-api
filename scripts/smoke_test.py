#!/usr/bin/env python3
"""Post-deploy smoke test verification script.

Runs as the gating check immediately after deployment to staging or production.
Validates /health, /ready, and optionally end-to-end OCR processing.

Usage:
    python scripts/smoke_test.py --base-url https://<org>-obliq-api-staging.hf.space
    python scripts/smoke_test.py --base-url http://localhost:8000 --api-key obliq_internal_test
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

# Minimal valid 1-page PDF file with text "Smoke Test Verification"
SAMPLE_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n"
    b"0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
)


def log(msg: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [SMOKE-TEST] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Obliq API Post-Deploy Smoke Verification")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"), help="API Base URL")
    parser.add_argument("--api-key", default=os.getenv("INTERNAL_KEY") or os.getenv("API_KEY"), help="API Key for E2E check")
    parser.add_argument("--timeout", type=float, default=30.0, help="Total timeout in seconds")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    api_key = args.api_key
    timeout = args.timeout

    log(f"Starting smoke verification against: {base_url}")

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        # 1. Health check
        log("Step 1: Checking /health...")
        try:
            resp = client.get("/health")
            if resp.status_code != 200:
                log(f"FAILED: /health returned status {resp.status_code}: {resp.text}")
                return 1
            health = resp.json()
            if health.get("status") != "ok":
                log(f"FAILED: /health payload invalid: {health}")
                return 1
            log(f"PASSED: /health is ok (version: {health.get('version', 'unknown')})")
        except Exception as exc:
            log(f"FAILED: Could not reach /health: {exc}")
            return 1

        # 2. Readiness check
        log("Step 2: Checking /ready...")
        try:
            resp = client.get("/ready")
            if resp.status_code != 200:
                log(f"FAILED: /ready returned status {resp.status_code}: {resp.text}")
                return 1
            ready = resp.json()
            if ready.get("status") not in ("ok", "ready"):
                log(f"FAILED: /ready indicates dependencies unready: {ready}")
                return 1
            log("PASSED: /ready dependencies are reachable (Database, Redis & OCR)")
        except Exception as exc:
            log(f"FAILED: Could not reach /ready: {exc}")
            return 1

        # 3. E2E Document Processing Check (if API key provided)
        if api_key:
            log("Step 3: Running End-to-End OCR job test...")
            headers = {"Authorization": f"Bearer {api_key}"}
            files = {"file": ("smoke_test.pdf", SAMPLE_PDF, "application/pdf")}

            try:
                # Submit
                submit_resp = client.post("/v1/jobs", headers=headers, files=files)
                if submit_resp.status_code != 202:
                    log(f"FAILED: Submit job returned status {submit_resp.status_code}: {submit_resp.text}")
                    if submit_resp.status_code == 401:
                        log(
                            "Check that INTERNAL_KEY is the full active key registered in the target "
                            "environment's database. GitHub's secret alone does not register the key."
                        )
                    return 1

                job_id = submit_resp.json().get("id")
                if not job_id:
                    log(f"FAILED: No job ID returned in submit response: {submit_resp.json()}")
                    return 1
                log(f"Job submitted successfully (job_id: {job_id})")

                # Poll
                start_time = time.time()
                status = "queued"
                while time.time() - start_time < timeout:
                    status_resp = client.get(f"/v1/jobs/{job_id}", headers=headers)
                    if status_resp.status_code != 200:
                        log(f"FAILED: Polling status returned {status_resp.status_code}: {status_resp.text}")
                        return 1

                    status_data = status_resp.json()
                    status = status_data.get("status")
                    if status in ("succeeded", "partial"):
                        break
                    if status == "failed":
                        log(f"FAILED: Job failed during OCR processing: {status_data}")
                        return 1
                    time.sleep(1)

                if status not in ("succeeded", "partial"):
                    log(f"FAILED: Job timed out after {timeout}s (last status: {status})")
                    return 1

                # Result
                result_resp = client.get(f"/v1/jobs/{job_id}/result", headers=headers)
                if result_resp.status_code != 200:
                    log(f"FAILED: Result returned {result_resp.status_code}: {result_resp.text}")
                    return 1

                result_data = result_resp.json()
                page_count = result_data.get("page_count", 0)
                log(f"PASSED: OCR job completed successfully ({page_count} page(s) processed)")
            except Exception as exc:
                log(f"FAILED: E2E OCR verification encountered exception: {exc}")
                return 1
        else:
            log("Step 3: Skipped E2E OCR check (no API key provided)")

    log("ALL SMOKE TESTS PASSED SUCCESSFULLY! Deployment is ready for traffic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
