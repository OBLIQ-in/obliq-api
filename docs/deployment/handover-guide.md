# Upstream Handover Guide: Continuous Deployment & Observability Setup

To activate the automated CI/CD pipeline on `OBLIQ-in/obliq-api`, the organization admin needs to complete two setup steps:
1. **Create the two Hugging Face Spaces (Staging & Production)**
2. **Configure GitHub Environments and Secrets**

---

### Step 1: Hugging Face Spaces Setup

The admin should navigate to [Hugging Face Space Creation](https://huggingface.co/new-space) and create two Spaces under the organization account (`OBLIQ-in`):

#### 1. Space Configurations
| Setting | Staging Space | Production Space |
| :--- | :--- | :--- |
| **Owner** | `OBLIQ-in` | `OBLIQ-in` |
| **Space Name** | `obliq-api-staging` | `obliq-api-production` |
| **Space SDK** | **Gradio** (Blank template) | **Gradio** (Blank template) |
| **Hardware** | **ZeroGPU Free** *(or CPU Basic if org has PRO)* | **ZeroGPU Free** *(or CPU Basic if org has PRO)* |
| **Visibility** | Public | Public |

#### 2. Space Secrets & Variables
In each Space, go to **Settings ➔ Variables and secrets**:

* **Secrets (click *New secret*):**
  - `DATABASE_URL`: Neon pooled connection string (`postgresql+asyncpg://...`)
  - `REDIS_URL`: Upstash TLS connection string (`rediss://...`)
  - `SECRET_KEY`: Secure random string (minimum 32 characters, e.g. generated via `openssl rand -hex 32`)

* **Variables (click *New variable*):**
  - `APP_ENV`: `staging` on the staging space, `production` on the production space.
  - `PORT`: `7860`
  - `LOG_LEVEL`: `INFO`

#### 3. Hugging Face Access Token
Generate an access token with **Write** permission at [Hugging Face Tokens](https://huggingface.co/settings/tokens) (e.g. named `github-actions-cd`). This allows GitHub Actions to push builds.

---

### Step 2: GitHub Repository Setup (`OBLIQ-in/obliq-api`)

In the GitHub repository, the admin needs to set up **Environments** and **Secrets**.

#### 1. Create GitHub Environments (`Settings ➔ Environments`)
1. **`staging`**:
   - No protection rules needed (auto-deploys upon merge to `main`).
2. **`production`**:
   - Check **Required reviewers** ➔ Add designated reviewers (`@abhirajadhikary06`, `@Naman-iitm`).
   - Configure **1 approval required** so that any single designated reviewer can approve the production deployment gate.
   - Leave **Prevent self-review** unchecked (`false`) to allow authorized maintainers to self-approve when initiating releases.

#### 2. Configure GitHub Secrets (`Settings ➔ Secrets and variables ➔ Actions`)

Under **Repository secrets** (available to all workflow stages), add:

| Secret Name | Description & Example Value |
| :--- | :--- |
| `HF_TOKEN` | Hugging Face access token with **Write** permission. |
| `HF_SPACE_STAGING` | `OBLIQ-in/obliq-api-staging` |
| `HF_SPACE_PRODUCTION` | `OBLIQ-in/obliq-api-production` |
| `DATABASE_URL` | Neon database connection string (used in CI for lightweight Alembic migrations). |
| `INTERNAL_KEY` | Active API key registered in the target database (see Step 3 below). |
| `ALERT_WEBHOOK_URL` *(Optional)* | Slack or Discord webhook URL for the 30-minute canary SLA alerts. |

---

### Step 3: Provision the `INTERNAL_KEY` for Smoke Verification

The smoke test submits a synthetic test PDF to verify the end-to-end OCR engine immediately after each deployment.

To create an active key:
1. Run the key creation script against the target database using the same `SECRET_KEY` configured in the Space:
   ```bash
   DATABASE_URL="<database-url>" SECRET_KEY="<space-secret-key>" PYTHONPATH=src python -m scripts.create_internal_key --org-id <organisation-uuid> --name "smoke-test-key"
   ```
2. Copy the printed full key (e.g. `obliq_internal_...` or `obliq_live_...`) and save it as the `INTERNAL_KEY` secret in GitHub.

---

### How the Pipeline Executes Once Merged

1. **Unit & Contract Tests**: Runs pytest suite in Python 3.11 with mocked singletons.
2. **Deploy to Staging**: Runs Alembic migrations, pushes code to `OBLIQ-in/obliq-api-staging`.
3. **Smoke Verification (Staging)**: Polls `/health`, verifies `/ready`, and runs end-to-end PDF OCR.
4. **Deploy to Production (Gated)**: Pauses and sends a notification for reviewer approval. Once approved, pushes to `OBLIQ-in/obliq-api-production`.
5. **Smoke Verification (Production)**: Validates production health, readiness, and OCR pipeline.
6. **Canary Monitoring (`canary.yml`)**: Runs every 30 minutes to verify character error rate ($\le 3\%$) and latency SLA ($\le 4.0\text{s}$).
