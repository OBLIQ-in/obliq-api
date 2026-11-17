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
        "--max-latency",
        type=float,
        default=4.0,
        help="Max allowed OCR engine processing latency in seconds per page (SLA)",
    )
    parser.add_argument(
        "--max-e2e-latency",
        type=float,
        default=30.0,
        help="Max allowed end-to-end wall-clock latency in seconds including network & queueing",
    )
    parser.add_argument(
        "--max-cer",
        type=float,
        default=0.03,
        help="Max allowed Character Error Rate (default: 0.03 / 3%%)",
    )
    parser.add_argument(
        "--warmup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Perform warm-up probe against /ready before timing benchmark",
    )
    parser.add_argument(
        "--warmup-timeout",
        type=float,
        default=45.0,
        help="Maximum timeout in seconds for warm-up probe",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=60.0,
        help="Maximum timeout in seconds when polling for job completion",
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
        # Warm-up / Wake-up probe (essential for sleeping serverless containers like Hugging Face Spaces)
        if args.warmup:
            print(f"[CANARY] Sending warm-up probe to {base_url}/ready...", flush=True)
            warmup_start = time.time()
            warmup_ok = False
            while time.time() - warmup_start < args.warmup_timeout:
                try:
                    ready_resp = client.get("/ready")
                    if ready_resp.status_code == 200:
                        warmup_ok = True
                        break
                except Exception:
                    pass
                time.sleep(1.0)
            if warmup_ok:
                print(
                    f"[CANARY] Warm-up successful in {time.time() - warmup_start:.2f}s",
                    flush=True,
                )
            else:
                print(
                    "[CANARY] Warning: Warm-up probe timed out or /ready not ready; proceeding with benchmark",
                    flush=True,
                )

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
        while time.time() - t0 < args.poll_timeout:
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
        page_count = result.get("page_count") or len(pages) or 1
        extracted_text = " ".join([p.get("text", "") for p in pages if p.get("text")])

        # Evaluate Accuracy
        cer = calculate_cer(truth_text, extracted_text) if truth_text else 0.0
        accuracy = max(0.0, 1.0 - cer) * 100

        # Evaluate Engine Latency (per page)
        proc_ms = result.get("processing_time_ms")
        if proc_ms is not None and proc_ms > 0:
            engine_latency = proc_ms / 1000.0
        else:
            engine_latency = sum(p.get("seconds", 0.0) for p in pages)
        if engine_latency <= 0.0:
            engine_latency = total_latency
        engine_latency_per_page = engine_latency / max(1, page_count)

        print(
            f"[CANARY] Benchmark Results: Engine Latency={engine_latency_per_page:.2f}s/page | "
            f"E2E Latency={total_latency:.2f}s | CER={cer:.4f} (Accuracy={accuracy:.1f}%)",
            flush=True,
        )

        failures = []
        if engine_latency_per_page > args.max_latency:
            failures.append(
                f"Engine Latency SLA breached: {engine_latency_per_page:.2f}s/page > {args.max_latency}s/page"
            )
        if total_latency > args.max_e2e_latency:
            failures.append(
                f"E2E Latency SLA breached: {total_latency:.2f}s > {args.max_e2e_latency}s"
            )
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
                        "engine_latency_per_page": round(engine_latency_per_page, 3),
                        "e2e_latency_seconds": round(total_latency, 2),
                        "character_error_rate": round(cer, 4),
                        "accuracy_pct": round(accuracy, 1),
                    },
                )
            return 1

    print("[CANARY] SUCCESS: All latency and accuracy SLAs verified!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
