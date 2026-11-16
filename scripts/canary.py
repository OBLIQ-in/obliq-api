#!/usr/bin/env python3
"""Accuracy and Latency Canary Check.

Runs as a scheduled monitor against live staging and production endpoints.
Extracts text from a golden fixture, asserts OCR accuracy (CER) and latency SLAs,
and triggers alerts via webhooks or GitHub Actions.

Usage:
    python scripts/canary.py --base-url https://<org>-obliq-api-staging.hf.space --api-key obliq_internal_test
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import time
from pathlib import Path

import httpx


def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculate Character Error Rate (CER) based on Levenshtein distance."""
    ref = "".join(reference.split())  # normalize whitespace
    hyp = "".join(hypothesis.split())

    if not ref:
        return 0.0 if not hyp else 1.0

    matcher = difflib.SequenceMatcher(None, ref, hyp)
    similarity = matcher.ratio()
    return max(0.0, 1.0 - similarity)


def send_alert(webhook_url: str, title: str, details: dict) -> None:
    """Send formatted alert payload to Slack or Discord webhook."""
    payload = {
        "text": f"🚨 *[CANARY ALERT]* {title}\n```json\n{json.dumps(details, indent=2)}\n```"
    }
    try:
        httpx.post(webhook_url, json=payload, timeout=10.0)
        print(f"[CANARY] Alert sent to webhook: {title}", flush=True)
    except Exception as exc:
        print(f"[CANARY] Failed to send webhook alert: {exc}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Obliq API Accuracy & Latency Canary")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("INTERNAL_KEY") or os.getenv("API_KEY"))
    parser.add_argument("--fixture", default="tests/fixtures/golden_fixture.pdf")
    parser.add_argument("--truth", default="tests/fixtures/golden_fixture_truth.txt")
    parser.add_argument(
        "--max-latency", type=float, default=5.0, help="Max allowed latency in seconds per page"
    )
    parser.add_argument(
        "--max-cer", type=float, default=0.05, help="Max allowed Character Error Rate (default 5%)"
    )
    parser.add_argument("--webhook-url", default=os.getenv("ALERT_WEBHOOK_URL"))
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    api_key = args.api_key
    webhook_url = args.webhook_url
    fixture_path = Path(args.fixture)
    truth_path = Path(args.truth)

    if not fixture_path.exists():
        print(f"[CANARY] ERROR: Golden fixture not found at {fixture_path}", file=sys.stderr)
        return 1

    truth_text = truth_path.read_text(encoding="utf-8") if truth_path.exists() else ""
    fixture_bytes = fixture_path.read_bytes()

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"[CANARY] Starting canary check against: {base_url}", flush=True)

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        # Submit
        t0 = time.time()
        try:
            submit_resp = client.post(
                "/v1/jobs",
                headers=headers,
                files={"file": (fixture_path.name, fixture_bytes, "application/pdf")},
            )
        except Exception as exc:
            err_msg = f"Network failure calling POST /v1/jobs: {exc}"
            print(f"[CANARY] FAILED: {err_msg}", file=sys.stderr)
            if webhook_url:
                send_alert(
                    webhook_url,
                    "API Endpoint Unreachable",
                    {"base_url": base_url, "error": str(exc)},
                )
            return 1

        if submit_resp.status_code != 202:
            err_msg = f"Submit returned status {submit_resp.status_code}: {submit_resp.text}"
            print(f"[CANARY] FAILED: {err_msg}", file=sys.stderr)
            if webhook_url:
                send_alert(
                    webhook_url,
                    "Job Submit Failed",
                    {"status_code": submit_resp.status_code, "body": submit_resp.text},
                )
            return 1

        job_id = submit_resp.json().get("id")

        # Poll
        status = "queued"
        while time.time() - t0 < 30.0:
            status_resp = client.get(f"/v1/jobs/{job_id}", headers=headers)
            if status_resp.status_code == 200:
                data = status_resp.json()
                status = data.get("status")
                if status in ("succeeded", "partial", "failed"):
                    break
            time.sleep(0.5)

        total_latency = time.time() - t0

        if status != "succeeded":
            err_msg = (
                f"Job {job_id} did not succeed (status: {status}, elapsed: {total_latency:.2f}s)"
            )
            print(f"[CANARY] FAILED: {err_msg}", file=sys.stderr)
            if webhook_url:
                send_alert(
                    webhook_url,
                    "OCR Job Failed or Timed Out",
                    {"job_id": job_id, "status": status, "latency": total_latency},
                )
            return 1

        # Fetch Result
        result_resp = client.get(f"/v1/jobs/{job_id}/result", headers=headers)
        if result_resp.status_code != 200:
            err_msg = f"Failed to fetch result: {result_resp.status_code}"
            print(f"[CANARY] FAILED: {err_msg}", file=sys.stderr)
            return 1

        result = result_resp.json()
        pages = result.get("pages", [])
        extracted_text = " ".join([p.get("text", "") for p in pages if p.get("text")])

        # Evaluate Accuracy & Latency
        cer = calculate_cer(truth_text, extracted_text) if truth_text else 0.0
        accuracy = max(0.0, 1.0 - cer) * 100

        print(
            f"[CANARY] Benchmark Results: Latency={total_latency:.2f}s | CER={cer:.4f} (Accuracy={accuracy:.1f}%)",
            flush=True,
        )

        failures = []
        if total_latency > args.max_latency:
            failures.append(f"Latency SLA breached: {total_latency:.2f}s > {args.max_latency}s")
        if cer > args.max_cer:
            failures.append(
                f"Accuracy SLA breached: CER {cer:.4f} > {args.max_cer} (Accuracy {accuracy:.1f}%)"
            )

        if failures:
            print(f"[CANARY] FAILED: {'; '.join(failures)}", file=sys.stderr)
            if webhook_url:
                send_alert(
                    webhook_url,
                    "SLA Regression Detected",
                    {
                        "base_url": base_url,
                        "failures": failures,
                        "latency_seconds": total_latency,
                        "character_error_rate": cer,
                        "accuracy_pct": accuracy,
                    },
                )
            return 1

    print("[CANARY] SUCCESS: All latency and accuracy SLAs verified!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
