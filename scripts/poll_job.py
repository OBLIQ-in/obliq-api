import httpx
import time
import sys

API_KEY = "obliq_live_M_IAcvGH97bXdthwEgA4WHhUt5tIqCGN"
JOB_ID  = sys.argv[1] if len(sys.argv) > 1 else "9750003f-62d6-44f3-a2fa-7ca4c887e282"
BASE    = "http://localhost:8000"
hdrs    = {"Authorization": f"Bearer {API_KEY}"}

print(f"Polling job {JOB_ID}...")
for i in range(360):
    r = httpx.get(f"{BASE}/v1/jobs/{JOB_ID}", headers=hdrs, timeout=10)
    j = r.json()
    status = j.get("status")
    pages  = j.get("page_count")
    err    = j.get("error_message")
    print(f"[{i*5}s] status={status}  pages={pages}  error={err}")
    if status in ("succeeded", "partial", "failed"):
        break
    time.sleep(5)
else:
    print("Timed out waiting for job")
    sys.exit(1)

if status == "failed":
    print("Job failed:", err)
    sys.exit(1)

# Fetch result
r = httpx.get(f"{BASE}/v1/jobs/{JOB_ID}/result", headers=hdrs, timeout=10)
result = r.json()
print(f"\nPages: {result['page_count']}  Device: {result.get('device')}  Status: {result['status']}")
for p in result["pages"]:
    conf = p.get("confidence")
    conf_str = f"{conf:.2f}" if conf is not None else "n/a"
    print(f"  Page {p['page_number']:>3} [{p.get('method','?'):>12}] conf={conf_str}  chars={p.get('n_chars',0):>5}  {p.get('seconds',0):.2f}s")
    if p.get("text"):
        preview = p["text"][:120].replace("\n", " ")
        print(f"             text: {preview}")
