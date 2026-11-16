# Contributing to obliq-api

Thank you for your interest in contributing to `obliq-api`! This repository hosts the high-throughput HTTP optical character recognition (OCR) and document extraction service designed for Chartered Accountant (CA) firms, compliance teams, and the OBLIQ platform.

Because this service processes documents containing financial records, invoices, and tax filings, code reviews strictly enforce tenant isolation, deterministic OCR outputs, rate limit adherence, and cryptographic token verification.

---

## 1. Development Setup

### Prerequisites
- **Python 3.11+**
- **Git**
- Optional: Local Docker or Redis instance (for local queue verification)

### Installation
1. Clone your fork and enter the workspace:
   ```bash
   git clone https://github.com/<your-username>/obliq-api.git
   cd obliq-api
   ```
2. Create and activate a Python 3.11 virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\Activate.ps1
   # macOS / Linux:
   source .venv/bin/activate
   ```
3. Install package in editable mode with development dependencies:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```
4. Copy the environment configuration file:
   ```bash
   cp .env.example .env
   ```

---

## 2. Privacy & Synthetic Data Policy

> [!CAUTION]
> **Strictly Synthetic Data Only**: Never commit, upload, or paste real taxpayer documents, PAN, GSTIN, Aadhaar numbers, client bank statements, or live API credentials in code, issues, PR discussions, fixtures, or test cases. All tests and fixtures must strictly use non-PII, synthetic test documents.

---

## 3. Branches and Commits

- **Branch Naming**: Branch from `main` using standard prefixes:
  - `feat/` for new features or capabilities
  - `fix/` for bug fixes and patches
  - `docs/` for documentation updates
  - `test/` for testing additions or improvements
  - `chore/` for maintenance, CI/CD, and dependency updates
  *Example*: `git checkout -b feat/pdf-page-extraction`
- **Conventional Commits**: Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
  - `feat: add streaming response for multi-page ocr`
  - `fix: handle corrupted pdf trailer gracefully`
  - `docs: update deployment environment reference`
  - `test: add contract tests for job status polling`
- Do not use `[skip ci]` in commit messages.

---

## 4. Pull Requests

1. **Run Verification Locally**:
   Ensure all unit and contract tests pass before pushing:
   ```bash
   pytest tests -v
   ```
2. **Open PR against `main`**:
   Fill out the Pull Request template completely. PRs without adequate descriptions or verification steps will be returned for revision.
3. **One Concern per PR**:
   Keep PRs focused and single-purpose. If your change depends on another unmerged PR, link it with `Depends on #<issue>` and mark it as a Draft PR.

---

## 5. Labels Guide

Each Issue and Pull Request carries a Type, an Area, and a Priority label. Automated workflows set some based on file paths and branch names; maintainers set the rest during triage.

| Group | Label | Description |
| :--- | :--- | :--- |
| **Type** | `bug` | Something isn't working or unexpected error |
| | `feature` | New feature or enhancement request |
| | `chore` | Maintenance tasks, dependency updates, and housekeeping |
| | `ci` | CI/CD and workflow changes |
| | `documentation` | Improvements or additions to documentation or runbooks |
| | `test` | Adding or updating test suites and test fixtures |
| | `arch` | Architecture decisions and design records |
| | `dependencies` | Pull requests that update a dependency file |
| | `github_actions` | Pull requests that update GitHub Actions code |
| | `breaking-change` | Introduces breaking API or schema changes |
| **Area** | `api` | Endpoints, request and response contract, versioning |
| | `ocr` | obliq-ocr engine boundary and extraction results |
| | `dashboard` | Developer dashboard, API keys, credits and usage graphs |
| | `security` | Authentication, secrets and security concerns |
| | `observability` | Logging, metrics, tracing, canary and alerting |
| | `privacy` | Data handling, PII and retention |
| | `reliability` | Error handling, retries, rollback and uptime |
| | `performance` | Speed, scaling, capacity and resource usage |
| | `deployment` | FastAPI Cloud apps, environments and releases |
| | `integration` | obliq-in-app client and contract tests |
| **Priority** | `high-priority` | High priority item |
| | `medium-priority` | Medium priority item |
| | `low-priority` | Low priority item |
| | `needs-triage` | Requires triage by maintainers |
| | `good first issue` | Good for newcomers to the project |
| **Phases** | `P-1` | Phase 1: Foundation |
| | `P-2` | Phase 2: Core API |
| | `P-3` | Phase 3: Security, privacy and API keys |
| | `P-4` | Phase 4: Reliability and observability |
| | `P-5` | Phase 5: Deployment |

---

## 6. Code Review Guidelines

- All PRs require at least 1 approving review from repository maintainers before merge.
- Maintainers review for:
  - Strict tenant and organization isolation.
  - Test coverage for newly introduced paths.
  - Synthetic test data compliance.
  - Zero-downtime database migration compatibility.
