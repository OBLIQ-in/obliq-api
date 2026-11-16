---
title: Obliq API
emoji: 🚀
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 4.44.1
python_version: "3.11"
app_file: app.py
pinned: false
---

# obliq-api

HTTP OCR service wrapping `obliq-ocr` (PyMuPDF + RapidOCR/ONNX), built for FastAPI Cloud.

## Stack

| Layer              | Service                          |
|--------------------|----------------------------------|
| Runtime            | Python 3.12 + FastAPI            |
| Database           | **Neon** (serverless Postgres)   |
| Job / rate store   | **Upstash** (managed Redis)      |
| Auth               | JWT (dashboard) + hashed API keys|
| Credits            | Organisation-scoped ledger       |

## Quick start

### 1. Create the managed services

**Neon (Postgres)**  
1. Go to https://console.neon.tech and create a project.  
2. Copy the **pooled** connection string.  
3. Change the driver prefix to `postgresql+asyncpg://` and keep `?sslmode=require`.

**Upstash (Redis)**  
1. Go to https://console.upstash.com and create a Redis database.  
2. Copy the **Redis URL** (it starts with `rediss://` — TLS is required).  
3. Paste it as `REDIS_URL`.

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+asyncpg://neondb_owner:npg_xxx@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
REDIS_URL=rediss://default:ASxx...@romantic-sheep-12345.upstash.io:6379
SECRET_KEY=a-long-random-string-at-least-32-characters
```

### 3. Install & migrate

```bash
pip install -e ".[dev]"
alembic upgrade head
```

### 4. Run

```bash
fastapi dev src/obliq_api/main.py
```

## Core endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | Liveness |
| GET | `/ready` | — | Readiness (Neon + Upstash + OCR) |
| POST | `/v1/auth/register` | — | Create org + owner |
| POST | `/v1/auth/login` | — | JWT tokens |
| POST | `/v1/jobs` | API key | Submit OCR job |
| GET | `/v1/jobs/{id}` | API key | Job status |
| GET | `/v1/jobs/{id}/result` | API key | Job result |
| POST | `/v1/keys` | JWT | Create API key |
| GET | `/v1/keys` | JWT | List keys |
| POST | `/v1/keys/{id}/revoke` | JWT | Revoke key |
| GET | `/v1/orgs/me` | JWT | Org + credit balance |
| GET | `/v1/orgs/me/ledger` | JWT | Credit ledger |
| GET | `/v1/orgs/me/usage` | JWT | Usage history |

## Design highlights

- **Neon** – durable data (orgs, users, API keys, credit ledger, usage records)
- **Upstash Redis** – ephemeral job state + results with automatic TTL (zero in-memory state)
- **Atomic credits** – reserve → settle / refund inside DB transactions
- **Ephemeral uploads** – temp files always deleted in `finally`
- **Internal keys** – exempt from credit deduction (`obliq_internal_`)
- **Typed errors** – single `ErrorResponse` shape with `request_id`

## Why Neon + Upstash?

| Concern | Neon | Upstash |
|---------|------|---------|
| Purpose | Durable, transactional data | High-churn job state & rate limits |
| Scale-to-zero friendly | Yes (serverless) | Yes (serverless) |
| TTL / auto-expiry | Not needed | Built-in |
| Large result payloads | Avoid | Ideal (short-lived) |
| Strong consistency | Required for credits | Eventual is fine for jobs |

## Checkpoints implemented

1. Repo structure, config, models, migrations, health/ready, typed schemas  
2. Auth (API keys + JWT), job flow, credit reservation/settlement, temp-file cleanup  
3. Structured error handling, request-id middleware, dashboard endpoints  

## Next steps

- Wire the real `obliq-ocr` package  
- Add rate-limit middleware (Upstash token bucket)  
- OpenTelemetry exporters  
- Daily usage rollups for graphs  
- Full dashboard frontend  
