import { ObliqError, ServerError } from "../errors.js";
import type {
  CreateJobOptions,
  JobStatusResponse,
  JobSubmitResponse,
  OCRResult,
  PollOptions,
} from "../types.js";

type FetchFn = (path: string, init?: RequestInit) => Promise<Response>;

export class JobsResource {
  constructor(private readonly request: FetchFn) {}

  /**
   * Submit a new document for OCR processing.
   */
  async create(options: CreateJobOptions): Promise<JobSubmitResponse> {
    const formData = new FormData();

    let blob: Blob;
    if (options.file instanceof Blob) {
      blob = options.file;
    } else if (options.file instanceof Uint8Array || options.file instanceof ArrayBuffer) {
      blob = new Blob([options.file], { type: "application/pdf" });
    } else {
      // Stream: read into chunks
      const reader = (options.file as ReadableStream<Uint8Array>).getReader();
      const chunks: Uint8Array[] = [];
      let done = false;
      while (!done) {
        const result = await reader.read();
        done = result.done;
        if (result.value) chunks.push(result.value);
      }
      blob = new Blob(chunks, { type: "application/pdf" });
    }

    const fileName = options.fileName || (options.file instanceof File ? options.file.name : "document.pdf");
    formData.append("file", blob, fileName);

    const headers: Record<string, string> = {};
    if (options.idempotencyKey) {
      headers["Idempotency-Key"] = options.idempotencyKey;
    }

    const response = await this.request("/v1/jobs", {
      method: "POST",
      body: formData,
      headers,
    });

    return (await response.json()) as JobSubmitResponse;
  }

  /**
   * Get the current status and metadata of an OCR job.
   */
  async get(jobId: string): Promise<JobStatusResponse> {
    const response = await this.request(`/v1/jobs/${jobId}`, {
      method: "GET",
    });
    return (await response.json()) as JobStatusResponse;
  }

  /**
   * Retrieve the final structured OCR extraction result of a completed job.
   */
  async getResult(jobId: string): Promise<OCRResult> {
    const response = await this.request(`/v1/jobs/${jobId}/result`, {
      method: "GET",
    });
    return (await response.json()) as OCRResult;
  }

  /**
   * Poll a job until it completes (`succeeded`, `partial`, or `failed`), with progress notifications.
   */
  async poll(jobId: string, options: PollOptions = {}): Promise<OCRResult> {
    const interval = options.pollIntervalMs ?? 1000;
    const timeout = options.timeoutMs ?? 120000;
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const status = await this.get(jobId);
      if (options.onProgress) {
        options.onProgress(status);
      }

      if (status.status === "succeeded" || status.status === "partial") {
        return await this.getResult(jobId);
      }

      if (status.status === "failed") {
        throw new ObliqError(
          status.error_code || "job_failed",
          status.error_message || "OCR job execution failed on worker",
          400
        );
      }

      await new Promise((resolve) => setTimeout(resolve, interval));
    }

    throw new ServerError(`Polling timed out after ${timeout}ms waiting for job ${jobId}`, 504);
  }
}
