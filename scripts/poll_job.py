"""Poll an OCR job without storing credentials or job IDs in source control.

Usage:
    INTERNAL_KEY=obliq_internal_... python scripts/poll_job.py <job-id>
    python scripts/poll_job.py <job-id> --base-url http://localhost:8000
"""

import argparse
import os
import sys
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll an Obliq OCR job")
    parser.add_argument("job_id")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("INTERNAL_KEY") or os.getenv("API_KEY"))
    args = parser.parse_args()
    if not args.api_key:
        parser.error("provide --api-key or set INTERNAL_KEY")

    headers = {"Authorization": f"Bearer {args.api_key}"}
    base_url = args.base_url.rstrip("/")
    print(f"Polling job {args.job_id}...")
    with httpx.Client(timeout=10) as client:
        for i in range(360):
            response = client.get(f"{base_url}/v1/jobs/{args.job_id}", headers=headers)
            response.raise_for_status()
            job = response.json()
            status = job.get("status")
            error = job.get("error_message")
            print(f"[{i * 5}s] status={status}  pages={job.get('page_count')}  error={error}")
            if status in ("succeeded", "partial", "failed"):
                break
            time.sleep(5)
        else:
            print("Timed out waiting for job")
            return 1

        if status == "failed":
            print("Job failed:", error)
            return 1

        response = client.get(f"{base_url}/v1/jobs/{args.job_id}/result", headers=headers)
        response.raise_for_status()
        result = response.json()
        print(f"\nPages: {result['page_count']}  Device: {result.get('device')}  Status: {result['status']}")
        for page in result["pages"]:
            confidence = page.get("confidence")
            confidence_text = f"{confidence:.2f}" if confidence is not None else "n/a"
            print(
                f"  Page {page['page_number']:>3} [{page.get('method', '?'):>12}] "
                f"conf={confidence_text}  chars={page.get('n_chars', 0):>5}  "
                f"{page.get('seconds', 0):.2f}s"
            )
            if page.get("text"):
                preview = page["text"][:120].replace("\n", " ")
                print(f"             text: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
