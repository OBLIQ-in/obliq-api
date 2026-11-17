import {
  AuthenticationError,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  PayloadTooLargeError,
  RateLimitError,
  ServerError,
  ValidationError,
  ObliqError,
} from "./errors.js";
import { DashboardResource } from "./resources/dashboard.js";
import { JobsResource } from "./resources/jobs.js";
import { KeysResource } from "./resources/keys.js";
import type { ClientOptions } from "./types.js";

export class ObliqClient {
  public readonly jobs: JobsResource;
  public readonly keys: KeysResource;
  public readonly dashboard: DashboardResource;

  private readonly apiKey?: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ClientOptions = {}) {
    this.apiKey = options.apiKey || (typeof process !== "undefined" ? process.env?.OBLIQ_API_KEY : undefined);
    this.baseUrl = (options.baseUrl || (typeof process !== "undefined" ? process.env?.OBLIQ_BASE_URL : undefined) || "https://api.obliq.in").replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 30000;
    this.maxRetries = options.maxRetries ?? 3;
    this.fetchImpl = options.fetch || fetch.bind(globalThis);

    const boundRequest = this.request.bind(this);
    this.jobs = new JobsResource(boundRequest);
    this.keys = new KeysResource(boundRequest);
    this.dashboard = new DashboardResource(boundRequest);
  }

  /**
   * Internal HTTP dispatcher with automatic exponential backoff, timeout handling, and typed error parsing.
   */
  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const headers = new Headers(init.headers);

    if (this.apiKey && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${this.apiKey}`);
    }

    let attempt = 0;
    while (true) {
      attempt++;
      let timeoutController: AbortController | undefined;
      let signal = init.signal;

      if (!signal && this.timeoutMs > 0) {
        timeoutController = new AbortController();
        const timeoutId = setTimeout(() => timeoutController?.abort(), this.timeoutMs);
        signal = timeoutController.signal;
        // Clean up timeout on exit
        const originalSignal = signal;
        originalSignal.addEventListener("abort", () => clearTimeout(timeoutId), { once: true });
      }

      try {
        const response = await this.fetchImpl(url, {
          ...init,
          headers,
          signal,
        });

        if (response.ok) {
          return response;
        }

        // Handle error responses
        const errorData = await response.json().catch(() => ({}));
        const message = errorData.error?.message || errorData.detail || response.statusText;
        const details = errorData.error?.details || errorData;

        if (response.status === 401) {
          throw new AuthenticationError(message, details);
        } else if (response.status === 403) {
          throw new ForbiddenError(message, details);
        } else if (response.status === 404) {
          throw new NotFoundError(message, details);
        } else if (response.status === 413) {
          throw new PayloadTooLargeError(message, details);
        } else if (response.status === 422) {
          throw new ValidationError(message, details);
        } else if (response.status === 429) {
          const retryAfter = Number(response.headers.get("Retry-After")) || 60;
          if (attempt <= this.maxRetries) {
            const backoffMs = Math.min(retryAfter * 1000, 5000 * Math.pow(2, attempt - 1));
            await new Promise((resolve) => setTimeout(resolve, backoffMs));
            continue;
          }
          throw new RateLimitError(retryAfter, details);
        } else if (response.status >= 500) {
          if (attempt <= this.maxRetries) {
            const backoffMs = 500 * Math.pow(2, attempt - 1) + Math.random() * 200;
            await new Promise((resolve) => setTimeout(resolve, backoffMs));
            continue;
          }
          throw new ServerError(message, response.status, details);
        }

        throw new ObliqError("api_error", message, response.status, false, details);
      } catch (err: unknown) {
        if (err instanceof ObliqError) {
          throw err;
        }
        if (attempt <= this.maxRetries) {
          const backoffMs = 500 * Math.pow(2, attempt - 1) + Math.random() * 200;
          await new Promise((resolve) => setTimeout(resolve, backoffMs));
          continue;
        }
        throw new NetworkError(err instanceof Error ? err.message : "Network request failed");
      }
    }
  }
}
