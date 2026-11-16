# Environments, Configuration, and Secrets Blueprint

## 1. Overview
`obliq-api` uses two completely isolated application environments hosted on Hugging Face Spaces:
- **Staging (`obliq-api-staging`)**: Pre-release verification, smoke testing, canary monitoring, and load benchmarking.
- **Production (`obliq-api-production`)**: Live production traffic consumed by the `obliq-in-app` Next.js client and external customers.

---

## 2. Environment Matrix

| Parameter | Staging Space (`obliq-api-staging`) | Production Space (`obliq-api-production`) |
| :--- | :--- | :--- |
| **Endpoint URL** | `https://<hf-org>-obliq-api-staging.hf.space` | `https://<hf-org>-obliq-api-production.hf.space` |
| **Custom Domain** | `api-staging.obliq.in` (optional CNAME) | `api.obliq.in` (via Cloudflare reverse proxy) |
| **Hardware Tier** | 2 vCPU · 16 GiB RAM (Free Space) | 2 vCPU · 16 GiB RAM (Free Space) |
| **`APP_ENV`** | `staging` | `production` |
| **Database (Neon)** | Dedicated branch: `staging` | Dedicated branch: `main` / `production` |
| **Redis (Upstash)** | Staging database / prefix `obliq:staging:` | Production database / prefix `obliq:prod:` |
| **Log Format** | Structured JSON | Structured JSON |
| **Deployment Gate** | Automatic on merge to `main` | Gated behind manual GitHub Environment approval |

---

## 3. Secrets Reference (Set in Space Settings ➔ Variables and Secrets)

> [!CAUTION]
> Never commit actual passwords, tokens, or connection strings to git. Set these strictly in the Hugging Face Space Settings.

| Secret Name | Required | Description & Format |
| :--- | :--- | :--- |
| `DATABASE_URL` | Yes | Pooled connection string from Neon: `postgresql+asyncpg://<user>:<password>@<ep-pooler>.<region>.aws.neon.tech/<dbname>?ssl=require` |
| `REDIS_URL` | Yes | Managed TLS connection string from Upstash: `rediss://default:<password>@<endpoint>.upstash.io:6379` |
| `SECRET_KEY` | Yes | Random 64-character hex or base64 string for JWT session and token signing. |
| `INTERNAL_KEY` | Yes | Internal service key formatted as `obliq_internal_<hex>` used for internal testing and canary calls. |

---

## 4. Public Variables Reference (Set in Space Settings ➔ Variables)

| Variable Name | Default | Allowed Values | Purpose |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `staging` | `staging`, `production`, `development` | Dictates error verbosity and telemetry routing. |
| `PORT` | `7860` | Integer (e.g. `7860`) | Listening port expected by Hugging Face Spaces. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Application logging verbosity. |
| `MAX_UPLOAD_SIZE_MB` | `50` | Integer (e.g. `50`) | Maximum allowable payload size for document uploads. |
| `MAX_PAGES_PER_JOB` | `200` | Integer (e.g. `200`) | Maximum page count allowed per document batch. |
| `JOB_RESULT_TTL_SECONDS` | `3600` | Integer (seconds) | Time-to-live for OCR results in Redis cache (1 hour). |

---

## 5. Free Quotas & Budget Guardrails

1. **Hugging Face Spaces**:
   - Hardware: 2 vCPU · 16 GiB RAM is $0.00 / month.
   - Sleep Policy: Free Spaces pause after 48h of inactivity. Canary crons (running every 30m) or uptime monitors keep staging/prod active.
2. **Neon PostgreSQL**:
   - Free tier includes 0.5 GiB storage and 100 max connections.
   - Using `-pooler` pooled connections ensures connection reuse across replicas.
3. **Upstash Redis**:
   - Free tier includes 10,000 commands/day. Automatic TTL on job results (`3600s`) ensures keys expire automatically without manual cleanup scripts.
