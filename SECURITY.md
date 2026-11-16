# Security Policy

`obliq-api` provides high-throughput document processing and optical character recognition (OCR) services for Chartered Accountant (CA) firms, compliance professionals, and the OBLIQ ecosystem. We take data confidentiality, tenant isolation, and cryptographic security seriously.

## Supported Versions

Only the latest release on the `main` branch receives active security updates and vulnerability patches.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

If you believe you have discovered a security vulnerability in `obliq-api`, please report it through private channels:

1. **GitHub Private Vulnerability Reporting (Preferred)**:
   Submit an advisory through [GitHub Security Advisories](https://github.com/OBLIQ-in/obliq-api/security/advisories/new).
2. **Email**:
   Send details directly to **security@obliq.in** or contact the repository maintainers.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please include:

- A clear description of the vulnerability and its potential impact.
- Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
- Affected endpoints, headers, or components.
- Any suggested remediations or mitigations if known.

> [!CAUTION]
> **Synthetic Data Only**: When creating a Proof of Concept (PoC) or reproduction steps, **strictly use synthetic data**. Never include real taxpayer identification numbers (PAN, GSTIN), real client financial records, or live secret keys.

## Response Timeline & SLA

- **Acknowledgment**: Within 48 hours of receipt.
- **Triage & Assessment**: Within 5 business days.
- **Remediation & Patching**: Critical security patches (P0/P1) are prioritized and deployed via staged rollouts with coordinated disclosure.

## Priority Focus Areas

We specifically encourage auditing and review in the following areas:

- **API Key & Token Security**: Cryptographic verification of BLAKE2b keyed API tokens, prefix length validation, and revocation integrity.
- **Tenant & Organization Isolation**: Ensuring document parsing jobs, cached results, and database records cannot be accessed across organization boundaries.
- **Payload & Memory Confidentiality**: Proper sanitization and ephemeral storage handling of uploaded client PDFs and images in memory/disk.
- **Rate Limiting & Denial of Service**: Resilience of CPU/GPU extraction workers against decompression bombs or malformed PDF payloads.
