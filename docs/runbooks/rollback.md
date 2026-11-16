# Runbook: Rollback Procedures and Incident Recovery

## 1. Overview
This runbook defines the emergency operational procedure to roll back an unhealthy deployment on Hugging Face Spaces or container platforms when post-deploy smoke verification fails or production incidents arise.

---

## 2. When to Roll Back vs Fix Forward

| Condition | Decision | Action |
| :--- | :--- | :--- |
| Smoke test fails post-deploy | **Instant Rollback** | Pipeline fails automatically; revert to previous stable commit. |
| Production 5xx spike (> 2% errors) | **Instant Rollback** | Roll back Space immediately; investigate offline. |
| Critical accuracy regression (CER > 5%) | **Instant Rollback** | Roll back Space to previous model/engine version. |
| Minor UI / doc bug, non-breaking | **Fix Forward** | Open bug issue, patch in staging, normal release cycle. |

---

## 3. Rollback Procedures

### Procedure A: Automated / Git-Based Rollback (Preferred)
Hugging Face Spaces continuously syncs and builds from its Git remote. To roll back:

1. **Identify the Last Known Good Commit:**
   ```bash
   git log --oneline -n 5
   ```
2. **Revert the Bad Commit in Git:**
   ```bash
   # Create a clean revert commit
   git revert HEAD --no-edit
   git push origin main
   ```
3. **Emergency Direct Push to Hugging Face Space (if bypassing GitHub Actions):**
   ```bash
   git push https://huggingface.co/spaces/<org>/obliq-api-production <good-commit-sha>:main --force
   ```
4. Hugging Face Spaces will immediately rebuild and redeploy the previous stable container image within 60–90 seconds.

---

### Procedure B: Dashboard Instant Rollback (Hugging Face Console)
1. Open the Hugging Face Space dashboard: `https://huggingface.co/spaces/<org>/obliq-api-production`.
2. Click **Files and versions** ➔ **History**.
3. Select the commit corresponding to the last healthy release.
4. Click **Revert this commit** or deploy from selected revision.
5. Watch the build logs until the status transitions to **Running**.

---

## 4. Database Migration Safety (Expand / Contract Pattern)

> [!IMPORTANT]
> Database migrations must **always be backward-compatible**. 
> A code rollback must NEVER require a database rollback.

- **Rule 1: Never drop columns or tables in the same release.** (Expand phase: add new optional column; Contract phase: drop old column in a later release).
- **Rule 2:** If a migration failed mid-way, inspect Alembic current head before taking action:
  ```bash
  alembic current
  ```
- **Rule 3:** Do not run `alembic downgrade` during a live emergency unless explicitly directed by the Database Lead, because down migrations risk data loss.

---

## 5. Post-Rollback Verification
Immediately after executing a rollback, run the smoke test script against the target environment:

```bash
python scripts/smoke_test.py --base-url https://<org>-obliq-api-production.hf.space --api-key $INTERNAL_KEY
```

Verify that:
- `/health` returns HTTP 200 `status: "ok"`
- `/ready` returns HTTP 200 `status: "ready"`
- End-to-end OCR processing returns HTTP 200 with valid page text.

---

## 6. Incident Communication Template

When a rollback is triggered, post this incident note to the team channel (Slack/Discord):

```text
🚨 [INCIDENT ALERT] Production Rollback Executed
Service: obliq-api-production
Trigger: [Smoke test failure / 5xx error spike / Accuracy regression]
Action Taken: Rolled back to commit [commit-sha]
Current Status: [Rebuilt / Running / Smoke test passing]
Impact: [Brief summary of duration and impacted requests]
Incident Lead: @[Your-Name]
Postmortem Issue: #[Issue-Number]
```
