export interface ClientOptions {
  /**
   * API Key (e.g. `obliq_live_...` or `obliq_internal_...`) or User JWT.
   */
  apiKey?: string;

  /**
   * Base URL of the Obliq API instance.
   * Defaults to `https://api.obliq.in` or `http://localhost:8000`.
   */
  baseUrl?: string;

  /**
   * Request timeout in milliseconds (default: 30000).
   */
  timeoutMs?: number;

  /**
   * Maximum number of retry attempts for network drops and 429/503 errors (default: 3).
   */
  maxRetries?: number;

  /**
   * Custom fetch implementation (optional, defaults to global `fetch`).
   */
  fetch?: typeof fetch;
}

export type JobStatus = "queued" | "processing" | "succeeded" | "partial" | "failed";

export interface CreateJobOptions {
  /**
   * Document payload: File, Blob, Buffer, Uint8Array, or ReadableStream.
   */
  file: Blob | File | Uint8Array | ArrayBuffer | ReadableStream<Uint8Array>;
  fileName?: string;
  maxPages?: number;
  idempotencyKey?: string;
}

export interface JobSubmitResponse {
  id: string;
  status: JobStatus;
}

export interface JobStatusResponse {
  id: string;
  status: JobStatus;
  page_count?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface OCRPage {
  page_number: number;
  text: string;
  confidence?: number;
  seconds?: number;
  method?: string;
  reason?: string;
  n_chars?: number;
  bounding_boxes?: unknown;
  error?: string | null;
}

export interface OCRResult {
  job_id: string;
  status: "succeeded" | "partial" | "failed";
  page_count: number;
  pages: OCRPage[];
  processing_time_ms?: number | null;
  device?: string | null;
}

export interface PollOptions {
  pollIntervalMs?: number;
  timeoutMs?: number;
  onProgress?: (status: JobStatusResponse) => void;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  expires_at?: string | null;
  is_internal: boolean;
  status: "active" | "expiring" | "revoked";
  created_at: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
}

export interface ApiKeyCreated {
  id: string;
  name: string;
  key_prefix: string;
  key: string; // Plaintext full key shown once
  scopes: string[];
  expires_at?: string | null;
  is_internal: boolean;
  created_at: string;
}

export interface CreateKeyOptions {
  name: string;
  scopes?: string[];
  expiresInDays?: number;
}

export interface RotateKeyOptions {
  gracePeriodHours?: number;
}

export interface DailyUsage {
  date: string;
  jobs: number;
  pages_processed: number;
  credits_charged: number;
  failed_jobs: number;
}

export interface HourlyUsage {
  hour: string;
  jobs: number;
  pages_processed: number;
  failed_jobs: number;
  avg_duration_ms: number;
}

export interface DashboardSummary {
  organisation: {
    id: string;
    name: string;
    slug?: string | null;
    credit_balance: number;
    status: string;
  };
  keys: {
    total: number;
    active: number;
  };
  usage_last_30_days: {
    jobs: number;
    pages_processed: number;
    credits_charged: number;
    failed_jobs: number;
  };
  recent_jobs: Array<{
    id: string;
    endpoint: string;
    status: string;
    pages_processed: number;
    credits_charged: number;
    created_at: string;
  }>;
}
