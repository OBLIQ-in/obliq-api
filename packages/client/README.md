# @obliq/client

Official TypeScript and JavaScript client library for **Obliq API** — High-performance Document OCR and Text Extraction.

## Features

- 🚀 **Isomorphic:** Runs in Node.js 18+, Bun, browsers, and Next.js (Server Components, Server Actions, Client Components).
- 🔒 **Type-Safe:** Complete TypeScript typings matching Obliq API schemas.
- ⚡ **Zero External Dependencies:** Built on native global `fetch` and standard `FormData`.
- 🔁 **Resilient:** Automatic exponential backoff with jitter on 429 rate limits, 503 transient errors, and network drops.
- ⏱️ **Ergonomic Polling:** Built-in polling helper (`client.jobs.poll(...)`) with progress callbacks.

---

## Installation

```bash
npm install @obliq/client
# or
pnpm add @obliq/client
# or
yarn add @obliq/client
```

---

## Quickstart

### 1. Initialize the Client

```typescript
import { ObliqClient } from "@obliq/client";

const obliq = new ObliqClient({
  apiKey: process.env.OBLIQ_API_KEY, // defaults to process.env.OBLIQ_API_KEY
  baseUrl: "https://api.obliq.in",   // defaults to https://api.obliq.in
});
```

### 2. Submit and Poll an OCR Job

```typescript
import { ObliqClient } from "@obliq/client";
import * as fs from "node:fs/promises";

const obliq = new ObliqClient();

// Submit document (accepts File, Blob, Buffer, or Uint8Array)
const fileBuffer = await fs.readFile("./invoice.pdf");
const job = await obliq.jobs.create({
  file: fileBuffer,
  fileName: "invoice.pdf",
});

console.log(`Job queued: ${job.id}`);

// Poll until completed with live progress callback
const result = await obliq.jobs.poll(job.id, {
  pollIntervalMs: 1000,
  timeoutMs: 60000,
  onProgress: (status) => console.log(`Current status: ${status.status}`),
});

console.log(`Processed ${result.page_count} pages in ${result.processing_time_ms}ms:`);
for (const page of result.pages) {
  console.log(`--- Page ${page.page_number} ---`);
  console.log(page.text);
}
```

### 3. Manage API Keys

```typescript
// List active workspace keys
const keys = await obliq.keys.list();

// Generate a new key with specific scopes and expiry
const newKey = await obliq.keys.create({
  name: "backend-microservice",
  scopes: ["ocr:read", "ocr:write"],
  expiresInDays: 90,
});
console.log(`Copy your API key now: ${newKey.key}`);

// Rotate key with a 24-hour grace period for zero downtime
const rotated = await obliq.keys.rotate(newKey.id, { gracePeriodHours: 24 });
console.log(`New key: ${rotated.key}`);

// Revoke a key
await obliq.keys.revoke(newKey.id);
```

### 4. Query Usage Analytics

```typescript
const summary = await obliq.dashboard.getSummary();
console.log(`Credit balance: ${summary.organisation.credit_balance}`);
console.log(`Total jobs last 30d: ${summary.usage_last_30_days.jobs}`);

const dailyUsage = await obliq.dashboard.getDailyUsage({ days: 7 });
console.table(dailyUsage);
```

---

## License

Apache-2.0
