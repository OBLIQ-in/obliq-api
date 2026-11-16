---
name: Testing & QA
about: Propose improvements or additions to unit tests, contract tests, load testing, or OCR accuracy benchmarks
title: "test: "
labels: ["test"]
assignees: ""
---

## Testing Scope

<!-- Which layer does this test target? -->
- [ ] Unit tests (`tests/unit/`)
- [ ] Contract tests (`tests/contract/`)
- [ ] Staging / Canary smoke verification (`scripts/smoke_test.py`)
- [ ] Load & stress testing (`tests/load/`)
- [ ] OCR extraction accuracy & latency benchmarks

## Problem / Gap Identified

<!-- What scenario, edge case, failure mode, or regression is currently unverified? -->

## Proposed Test Plan & Fixtures

<!-- Describe the synthetic fixtures, mock services, or test cases to be implemented. -->

## Privacy Confirmation

- [ ] All test inputs, fixtures, and golden truths will strictly use synthetic, non-PII documents.
