import type {
  ApiKey,
  ApiKeyCreated,
  CreateKeyOptions,
  RotateKeyOptions,
} from "../types.js";

type FetchFn = (path: string, init?: RequestInit) => Promise<Response>;

export class KeysResource {
  constructor(private readonly request: FetchFn) {}

  /**
   * List all active and revoked API keys in the current workspace.
   */
  async list(): Promise<ApiKey[]> {
    const response = await this.request("/v1/keys", {
      method: "GET",
    });
    const data = (await response.json()) as { keys: ApiKey[] };
    return data.keys;
  }

  /**
   * Generate a new API key.
   * Note: The plaintext key secret is only returned in this response and cannot be retrieved again.
   */
  async create(options: CreateKeyOptions): Promise<ApiKeyCreated> {
    const response = await this.request("/v1/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: options.name,
        scopes: options.scopes ?? ["ocr:read", "ocr:write"],
        expires_in_days: options.expiresInDays,
      }),
    });
    return (await response.json()) as ApiKeyCreated;
  }

  /**
   * Atomically rotate an API key with an optional grace period.
   */
  async rotate(keyId: string, options: RotateKeyOptions = {}): Promise<ApiKeyCreated> {
    const response = await this.request(`/v1/keys/${keyId}/rotate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grace_period_hours: options.gracePeriodHours ?? 24,
      }),
    });
    return (await response.json()) as ApiKeyCreated;
  }

  /**
   * Revoke an active API key immediately.
   */
  async revoke(keyId: string): Promise<void> {
    await this.request(`/v1/keys/${keyId}/revoke`, {
      method: "POST",
    });
  }
}
