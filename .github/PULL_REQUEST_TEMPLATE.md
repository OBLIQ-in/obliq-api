## Summary

<!-- Briefly describe what this PR changes, why, and which issue it addresses. -->

Closes #
Depends on: #

## Type of Change

- [ ] `feat`: New feature or capability
- [ ] `fix`: Bug fix or defect resolution
- [ ] `refactor`: Code refactoring without behavior change
- [ ] `perf`: Performance improvement
- [ ] `test`: Added or updated tests (unit, contract, load)
- [ ] `docs`: Documentation update or runbook addition
- [ ] `ci`: CI/CD workflows, build scripts, or developer tooling
- [ ] `chore`: Maintenance, dependencies, or configuration

## Testing & Verification

<!-- Describe how these changes were verified. Include pytest outputs, smoke verification logs, or commands executed. -->

- [ ] Unit & contract tests pass locally (`pytest tests -v`)
- [ ] Synthetic test fixtures only (no real financial/client PII)
- [ ] Tested against local or staging environment

## Architectural & Security Checklist

- [ ] Organization & tenant isolation preserved across all modified queries/routes
- [ ] Input validation applied to all API schemas and file upload endpoints
- [ ] Secrets and credentials are NOT committed to source control
- [ ] Database migrations (if any) are backward-compatible and tested
- [ ] Commit history is clean and follows Conventional Commits format
