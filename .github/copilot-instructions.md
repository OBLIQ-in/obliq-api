# GitHub Copilot Instructions for obliq-api

This repository contains **obliq-api**, a high-performance FastAPI microservice wrapping the `obliq-ocr` engine (RapidOCR + PyMuPDF), built to process mixed-format tax documents, invoices, bills, and challans uniformly across distributed enterprise services for small and mid-sized CA firms at [OBLIQ.in](https://obliq.in).

When assisting with code generation, chat, or reviewing pull requests, strictly adhere to the standards, architecture, and constraints below.

---

## 1. Architectural Guidelines & Async Discipline

- **Framework & Runtime:** Python 3.11 (`>=3.11,<3.12`), FastAPI, Uvicorn/Gunicorn on Hugging Face Spaces (ZeroGPU / CPU).
- **Asynchronous Execution:** 
  - All route handlers, service methods, database queries, and Redis calls must be fully asynchronous (`async` / `await`).
  - **No Blocking Operations in Async Handlers:** Heavy synchronous CPU work (such as OCR extraction, large PDF page rendering, or disk hashing) must never run bare in an async handler. Always offload to background threads (`asyncio.to_thread`) or background workers.
  - Blocking filesystem calls (like `pathlib.Path.mkdir` or synchronous file read/write) inside async routes should be handled with caution to prevent event loop starvation.
- **Dependencies & Singletons:**
  - Inject services using FastAPI's dependency injection system (`Depends(...)`).
  - Avoid global mutable state. Use accessors in `obliq_api.dependencies` (e.g., `get_job_store`, `get_rate_limiter`, `get_ocr_engine`, `get_db`).

---

## 2. Multi-Tenancy & Security Rules

- **Strict Tenant & Organization Isolation:**
  - Every authenticated request is scoped to an `organisation_id` via `AuthContext`.
  - Database queries involving tenant-owned resources (API keys, jobs, usage records, credits) **must explicitly filter by `organisation_id`**. Never rely on client-supplied IDs without verifying organization ownership.
- **Authentication & API Keys:**
  - Live keys start with prefix `obliq_live_`; internal service keys start with `obliq_internal_`.
  - **API Token Hashing vs. Password Hashing:**
    - High-entropy API keys (144 bits of randomness via `secrets.token_urlsafe(24)`) use fast keyed hashing (`hashlib.blake2b` / HMAC) for high-throughput lookup performance without CPU denial-of-service. Do NOT suggest replacing fast keyed token lookups with slow password-hashing algorithms like bcrypt.
    - User account passwords (human-entered) are strictly hashed using bcrypt via `passlib.context.CryptContext` in `src/obliq_api/auth/keys.py`.
- **Zero Committed Secrets:**
  - Never commit credentials, connection strings, JWT secrets, or tokens to the repository.
  - All secrets must be loaded through `obliq_api.config.Settings` (Pydantic Settings reading environment variables).
- **Document Privacy & Ephemeral Storage:**
  - Uploaded tax files and invoices contain sensitive financial PII.
  - Temporary files created during extraction must be stored in isolated directories and **guaranteed to be deleted** in a `finally` block or context manager upon completion or failure.

---

## 3. API Contract & Error Handling

- **Unified Error Envelope:**
  All error responses (4xx and 5xx) must conform to the unified error schema defined in `obliq_api.schemas.common.ErrorResponse`:
  ```json
  {
    "error": {
      "code": "invalid_api_key",
      "message": "The provided API key is invalid or revoked.",
      "details": []
    }
  }
  ```
- **Custom Exceptions:**
  - All domain and application exceptions must inherit from `ObliqError` in `obliq_api.exceptions` (e.g., `AuthenticationError`, `RateLimitExceededError`, `NotFoundError`, `PayloadTooLargeError`, `UnsupportedMediaTypeError`).
  - Exceptions map to standardized HTTP status codes and machine-readable error codes. Do not return bare strings or non-standard error structures.

---

## 4. Database Models & SQLAlchemy 2.0

- **SQLAlchemy 2.0 Typing:**
  - Use `Mapped[...]` and `mapped_column(...)` exclusively for ORM models.
  - For UUID primary/foreign keys in PostgreSQL, use Python's native `uuid.UUID` in type annotations:
    ```python
    import uuid
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ```
    *Never use dialect `Mapped[UUID]` directly as a mapped type, as this breaks Mypy static analysis.*
- **Migrations:**
  - Any database schema modification must be accompanied by an Alembic migration in `alembic/versions/`.
  - Migrations must be backward-compatible (non-blocking for rolling deployments).

---

## 5. Code Quality, Typing & Testing Standards

- **Code Formatting & Linting:**
  - Formatted and linted using **Ruff** with line length 100 (`target-version = "py311"`).
  - Code must pass `ruff check .` and `ruff format --check .` cleanly.
- **Type Safety:**
  - Strict type hints on all public functions, classes, and router endpoints.
  - Must pass `mypy src` with zero errors.
- **Testing & Coverage:**
  - Tests use `pytest` and `pytest-asyncio`.
  - Minimum test coverage requirement is **60.0%** (enforced in CI with `--cov=obliq_api`).
  - Unit and contract tests must never connect to live external dependencies (Neon PostgreSQL, Upstash Redis, or Hugging Face Spaces). Always use the mock fixtures defined in `tests/conftest.py` (`MockJobStore`, `MockRateLimiter`, `MockOCREngine`, mock database session).
  - Test files must use synthetic dummy fixtures (e.g. `tests/fixtures/golden_fixture.pdf`), never real client documents or financial data.

---

## 6. Git & Pull Request Guidelines

- **Conventional Commits:**
  - All commit messages and PR titles must adhere to Conventional Commits:
    `feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `ci:`, `chore:`.
- **Review Scope:**
  - When reviewing pull requests, prioritize:
    1. Tenant isolation & data privacy (financial document safety).
    2. Async performance (preventing event loop blocking).
    3. Error handling consistency (unified envelope).
    4. Test coverage & mock isolation.
