"""End-to-end test script for obliq-api.

Run after the server is started fresh:
    fastapi dev src/obliq_api/main.py

Usage:
    python scripts/test_flow.py [path/to/file.pdf]
"""

import sys
import time

import httpx

BASE = "http://localhost:8000"
EMAIL = "test@example.com"
PASSWORD = "password123"
PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else "sample/sample-file.pdf"

client = httpx.Client(base_url=BASE, timeout=60)


def banner(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── 1. Login ──────────────────────────────────────────────────
banner("1. Login")
r = client.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
if r.status_code != 200:
    # Try registering if login fails
    r = client.post(
        "/v1/auth/register",
        json={
            "organisation_name": "Test Org",
            "email": EMAIL,
            "password": PASSWORD,
        },
    )
    if r.status_code not in (200, 201):
        print("Register failed:", r.text)
        sys.exit(1)

token = r.json()["access_token"]
print(f"JWT: {token[:40]}...")
dashboard_headers = {"Authorization": f"Bearer {token}"}

# ── 2. Create API key ─────────────────────────────────────────
banner("2. Create API key")
r = client.post("/v1/keys", headers=dashboard_headers, json={"name": "test-key"})
if r.status_code != 201:
    print("Create key failed:", r.text)
    sys.exit(1)

api_key = r.json()["key"]
print(f"API key: {api_key}")
job_headers = {"Authorization": f"Bearer {api_key}"}

# ── 3. Health / ready ─────────────────────────────────────────
banner("3. Health checks")
print("GET /health  :", client.get("/health").json())
print("GET /ready   :", client.get("/ready").json())

# ── 4. Submit OCR job ─────────────────────────────────────────
banner(f"4. Submit job  ({PDF_PATH})")
with open(PDF_PATH, "rb") as f:
    r = client.post(
        "/v1/jobs",
        headers=job_headers,
        files={"file": (PDF_PATH.split("/")[-1], f, "application/pdf")},
        timeout=30,
    )

if r.status_code != 202:
    print("Submit failed:", r.text)
    sys.exit(1)

job = r.json()
job_id = job["id"]
print(f"Job ID : {job_id}")
print(f"Status : {job['status']}")

# ── 5. Poll until terminal ────────────────────────────────────
banner("5. Polling job status")
for i in range(720):  # up to 60 minutes
    time.sleep(5)
    r = client.get(f"/v1/jobs/{job_id}", headers=job_headers, timeout=10)
    j = r.json()
    status = j.get("status")
    pages = j.get("page_count", "?")
    print(f"  [{i * 5:>5}s] status={status:<12} pages={pages}")
    if status in ("succeeded", "partial", "failed"):
        break
else:
    print("Timed out polling job")
    sys.exit(1)

if status == "failed":
    print("Job FAILED:", j.get("error_message"))
    sys.exit(1)

# ── 6. Fetch result ───────────────────────────────────────────
banner("6. OCR result")
r = client.get(f"/v1/jobs/{job_id}/result", headers=job_headers, timeout=10)
result = r.json()
print(f"Pages  : {result['page_count']}")
print(f"Device : {result.get('device')}")
print(f"Status : {result['status']}")
print(f"Time   : {result.get('processing_time_ms')} ms")
print()
for p in result["pages"]:
    conf = p.get("confidence")
    conf_str = f"{conf:.2f}" if conf is not None else " n/a"
    text_preview = (p.get("text") or "")[:80].replace("\n", " ")
    print(
        f"  Page {p['page_number']:>3}  [{p.get('method', '?'):>12}]  conf={conf_str}  {p.get('seconds', 0):.1f}s  chars={p.get('n_chars', 0):>5}"
    )
    if text_preview:
        print(f'           "{text_preview}"')

# ── 7. Credits ────────────────────────────────────────────────
banner("7. Credit balance")
r = client.get("/v1/orgs/me", headers=dashboard_headers, timeout=10)
org = r.json()
print(f"Balance : {org['credit_balance']}")

# ── 8. Ledger ─────────────────────────────────────────────────
banner("8. Credit ledger (last 5 entries)")
r = client.get("/v1/orgs/me/ledger", headers=dashboard_headers, timeout=10)
for entry in r.json()["items"][:5]:
    print(
        f"  {entry['entry_type']:<8}  amount={entry['amount']:>+7}  balance_after={entry['balance_after']}"
    )

# ── 9. Dashboard summary ──────────────────────────────────────
banner("9. Dashboard summary")
r = client.get("/v1/dashboard/summary", headers=dashboard_headers, timeout=10)
s = r.json()
print(f"Balance        : {s['organisation']['credit_balance']}")
print(f"Active keys    : {s['keys']['active']} / {s['keys']['total']}")
print(f"30d jobs       : {s['usage_last_30_days']['jobs']}")
print(f"30d pages      : {s['usage_last_30_days']['pages_processed']}")
print(f"30d credits    : {s['usage_last_30_days']['credits_charged']}")
print(f"30d failures   : {s['usage_last_30_days']['failed_jobs']}")

# ── 10. Daily usage ───────────────────────────────────────────
banner("10. Daily usage (last 7 days)")
r = client.get("/v1/dashboard/usage/daily?days=7", headers=dashboard_headers, timeout=10)
for day in r.json()["days"]:
    print(
        f"  {day['date']}  jobs={day['jobs']}  pages={day['pages_processed']}  credits={day['credits_charged']}"
    )

print("\n✓ All endpoints tested successfully")
client.close()
