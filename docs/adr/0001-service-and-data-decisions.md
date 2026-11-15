# ADR 0001: Service & Data Decisions

## Status
Accepted

## Context
obliq-in-app (Next.js) cannot import the Python `obliq-ocr` package. The OCR engine must be served over HTTP. The service must also support multi-tenant API keys, credits, and a developer dashboard. The platform (FastAPI Cloud) scales replicas independently and supports scale-to-zero, so no job state may live in process memory.

## Decisions

1. **HTTP service** – FastAPI on FastAPI Cloud wrapping `obliq-ocr`.
2. **Primary database** – **Neon** (serverless PostgreSQL) for organisations, users, API keys, credit ledger, and usage records. Use the pooled connection string with `sslmode=require`.
3. **Job store** – **Upstash Redis** (managed, TLS via `rediss://`) for job status and results, with automatic TTL. Zero in-memory job state across replicas.
4. **Account model** – Organisation / firm is the billing entity. Users belong to organisations. Credits and API keys are scoped to the organisation.
5. **Dashboard auth** – Simple JWT (access + refresh). No Auth0 for v1.
6. **API keys** – High-entropy keys with prefix `obliq_live_` (customer) / `obliq_internal_` (service). Full key shown once; only hash + prefix stored.
7. **Credits** – Starting grant 10 000. 1 credit per page. Reserve at submit, settle on success, refund on failure. Internal keys exempt. Append-only ledger is source of truth.
8. **Ephemeral storage** – Never persist uploaded documents. Temp files deleted in `finally`.
9. **Versioning** – All endpoints under `/v1` except `/health` and `/ready`.

## Consequences
- Clean separation behind protocols (OCREngine, JobStore) enables contract tests and future engine swaps.
- Organisation model allows future team/role expansion without schema rewrite.
- Upstash TTL automatically expires old results; no manual cleanup job required for results.
- Neon pooled connections keep the service scale-to-zero friendly.
