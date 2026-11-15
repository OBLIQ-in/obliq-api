# Architecture Decision & Capacity Plan: Scaling, Concurrency, and Resource Sizing

## 1. Overview
`obliq-api` wraps `obliq-ocr` (PyMuPDF for document rasterization + RapidOCR / ONNX runtime for text detection and recognition). OCR processing is intensely CPU-bound and memory-sensitive. This document defines the capacity, concurrency limits, cold-start mitigation, and connection pool sizing for the service across environments.

---

## 2. Memory & Hardware Sizing

### 2.1 Component Memory Footprint per Job
Benchmarking shows the baseline memory consumption breakdown during an OCR run:

| Component | Resident Memory (RSS) | Description |
| :--- | :--- | :--- |
| **Python Base Runtime** | ~100 MiB | FastAPI, Uvicorn, SQLAlchemy, Pydantic, structlog |
| **RapidOCR ONNX Models** | ~180 MiB | Text detection, direction classification, and recognition models |
| **PyMuPDF Page Rasterization** | ~60 MiB | 300 DPI pixmap rendering for scanned pages |
| **OS & Container Buffers** | ~40 MiB | Memory headroom |
| **Peak Total for 1 Job** | **~380 MiB** | Peak memory for 1 active document |

### 2.2 Instance Comparison Matrix

| Provider / Tier | vCPU | RAM | Concurrency Limit | Peak Parallel Jobs | Risk Assessment / Fit |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FastAPI Cloud (Nano)** | 0.5 shared | 512 MiB | 1 | 1 | **High Risk**: 380 MiB is 74% of 512 MiB. 2 concurrent jobs trigger OOM crash (Exit 137). |
| **FastAPI Cloud (Small)** | 1.0 dedicated | 2 GiB | 2 | 2 | **Low Risk**: $2 \times 380\text{ MiB} = 760\text{ MiB}$, safely below 2 GiB. |
| **FastAPI Cloud (Medium)**| 2.0 dedicated | 4 GiB | 4 | 4 | **Optimal**: Supports up to 4 concurrent jobs with headroom. |
| **Hugging Face Spaces (Free)**| 2.0 dedicated | **16 GiB** | **4 to 6** | **6** | **Zero Risk**: 16 GiB eliminates OOM crashes completely for \$0/mo. |

---

## 3. Replicas, Cold Starts & Availability

### 3.1 Free Tier (Staging / Dev)
- **Min Replicas:** `0` (Scales to zero when idle).
- **Max Replicas:** `2`
- **Cold Start:** ~10–18 seconds on initial request after idle (time to boot Python, initialize dependencies, and load ONNX weights).
- **Keep-Alive:** An automated cron or canary ping every 24 hours prevents sleep if continuous readiness is required.

### 3.2 Production (Pro Tier / Hugging Face Persistent)
- **Min Replicas:** `1` (Always-on, eliminating cold starts).
- **Max Replicas:** `5` to `10`
- **Scale-Up Trigger:** Scale when average CPU exceeds 75% or request queue depth exceeds 2 jobs for 60 seconds.

---

## 4. Concurrency & Statelessness

### 4.1 Strict Concurrency Enforcement
To prevent memory exhaustion, each replica strictly bounds its active OCR workers via `ProcessPoolExecutor`:
- **Nano (512MB):** Concurrency = **1**.
- **Small (2GB):** Concurrency = **2**.
- **Hugging Face (16GB):** Concurrency = **4**.

### 4.2 Stateless Verification
The service is completely stateless:
1. **Job Status & Results:** Stored exclusively in **Upstash Redis** with an automatic TTL (`job_result_ttl_seconds`, default 3600s). No replica keeps job memory.
2. **Billing & Authentication:** Kept exclusively in **Neon PostgreSQL** (append-only ledger).
3. **Ephemeral Files:** Uploaded files reside only in temporary disk storage (`obliq_uploads/`) and are deterministically unlinked in `finally` blocks. Startup sweeps purge orphaned files older than 30 minutes.

---

## 5. Database Connection Capacity (Neon Serverless)

Neon PostgreSQL employs connection limits on serverless endpoints (typically 100 max connections on pooled endpoints):
- Each replica is configured with:
  - `database_pool_size = 3`
  - `database_max_overflow = 2`
  - Maximum connections per replica = `5`.
- **At Peak Scaling (10 Replicas):**
  $$10 \text{ replicas} \times 5 \text{ max connections} = 50 \text{ connections}$$
  Safely below the 100-connection limit.
- **Pooled Connection Requirement:** Always use the `-pooler` connection string (`sslmode=require`) to utilize Neon's built-in PgBouncer pooling.

---

## 6. Capacity Targets & Rate Limits

Agreed service level targets with `obliq-in-app`:

| Metric | Target (Single Replica) | Target (3 Replicas Scale) |
| :--- | :--- | :--- |
| **Page Throughput** | 12–15 pages / minute | 36–45 pages / minute |
| **Peak Concurrent Documents** | 1–4 documents | 3–12 documents |
| **P95 Latency (Digital PDF)** | < 300 ms / page | < 300 ms / page |
| **P95 Latency (Scanned 300 DPI)** | < 3.5 s / page | < 3.5 s / page |

---

## 7. Over-Capacity Handling (Graceful Degradation)

When the service reaches maximum capacity:
1. **Never Crash:** Requests beyond active capacity must be rejected early before consuming memory.
2. **Response:** Return HTTP `429 Too Many Requests` (or `503 Service Unavailable`) with header:
   ```http
   Retry-After: 15
   Content-Type: application/json
   
   {
     "error": {
       "code": "rate_limit_exceeded",
       "message": "Service is at capacity. Please retry shortly.",
       "retryable": true,
       "details": { "retry_after": 15 }
     }
   }
   ```
3. `obliq-in-app` automatically respects `Retry-After` and retries with exponential backoff.

---

## 8. Scaling Alarms & Observability

Monitored through OpenTelemetry instruments:
- **Memory Alert:** Alert when container memory exceeds **80%** for > 2 minutes.
- **CPU Alert:** Alert when sustained CPU exceeds **90%** for > 3 minutes.
- **Saturation Alert:** Alert when active replicas = `MAX_REPLICAS` and job queue latency exceeds 30 seconds.

---

## 9. Monthly Cost Projections

| Setup | Infrastructure | Estimated Cost |
| :--- | :--- | :--- |
| **Option A (Hugging Face Free Spaces)** | 2 vCPU, 16 GB RAM + Neon Free + Upstash Free | **\$0.00 / month** |
| **Option B (FastAPI Cloud Free - Nano)** | 0.5 vCPU, 512 MB RAM + Neon Free + Upstash Free | **\$0.00 / month** |
| **Option C (FastAPI Cloud Pro - Small)** | 1.0 vCPU, 2 GB RAM (1 always-on) | **~\$15.00 – \$25.00 / month** |
| **Option D (High Volume / Scale)** | 2.0 vCPU, 4 GB RAM (up to 5 replicas) | **~\$60.00 – \$100.00 / month** |

---

## 10. Large Document Contingency (Chunking Plan)

If a single document exceeds 50 pages:
1. `max_pages_per_job` enforces an immediate limit (default 200 pages; capped at 50 on constrained tiers).
2. For documents > 50 pages, the OCR worker processes pages sequentially in batches of 10, freeing memory pixmaps between batches using `fitz` pixmap garbage collection.
